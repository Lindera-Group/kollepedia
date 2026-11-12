"""Migrate the prototype database into the NG schema — a semantic translation.

Implements the prototype → NG mapping (see docs/ARKITEKTUR.md):

  Term                     → Concept + one initial Version (dated to the
                             collection's publication year; real import
                             timestamp preserved in provenance)
  TermSection + Author     → 'section' + 'author' annotations with real offsets
  Variant                  → 'variant' annotations (span 0-0)
  Translation              → translated_from VersionEdge (en child ← sv parent)
  CrossRef / disambiguation→ related_to ConceptRelations with notes
  confidence_score         → 'confidence' annotation
  categories / parts       → version tags (part:<code> for Transmodel)

Usage:
    uv run python scripts/migrate_from_prototype.py [path-to-prototype-db]

The prototype DB is opened READ-ONLY. The NG database is dropped and
recreated, so the script is idempotent.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import unicodedata
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Annotation,
    Base,
    Collection,
    ConceptRelation,
    User,
    VersionEdge,
)

# The real source collections; test/seed/private prototype collections stay behind.
MIGRATED_SLUGS = [
    "kollektivtrafikordboken-2008",
    "kollepedia-2012",
    "transmodel-2021",
    "ordbok-framtidens-resande-2024",
    "samtrafiken-begreppslista-2024",
    "trafikverket-jarnvagstermer-2025",
]

STATUS_MAP = {
    "pending": "draft",
    "reviewed": "proposed",
    "approved": "proposed",
    "rejected": "deprecated",
}

RELATION_MAP = {
    "see_also": "related_to",
    "related": "related_to",
    "broader": "broader",
    "narrower": "narrower",
}

PROTOTYPE_IMPORT_HANDLE = "prototype-import"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "user"


def section_sort_key(section_number: str) -> tuple[int, str]:
    try:
        return (int(section_number), "")
    except ValueError:
        return (10**9, section_number)


def open_old_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main() -> None:
    # The source path is explicit (argument or PROTOTYPE_DB) — this script
    # DROPS the NG schema, so it must never run against a guessed source.
    old_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROTOTYPE_DB", "")
    if not old_path:
        raise SystemExit("Usage: migrate_from_prototype.py <old-db> (or set PROTOTYPE_DB).")
    old = open_old_db(old_path)

    print(f"Source (read-only): {old_path}")
    print(f"Target: {engine.url}")

    # branches ↔ versions form an FK cycle, so drop with FK enforcement off
    # (idempotency: the whole NG schema is rebuilt from scratch on every run).
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Can't sort tables for DROP")
        with engine.connect() as conn:
            if engine.url.get_backend_name() == "sqlite":
                conn.execute(text("PRAGMA foreign_keys=OFF"))
            Base.metadata.drop_all(bind=conn)
            conn.commit()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ---------------------------------------------------------------- users
    author_rows = old.execute(
        "SELECT author_id, name, affiliation, web_url FROM authors ORDER BY name"
    ).fetchall()
    users_by_author_id: dict[str, User] = {}
    users_by_name: dict[str, User] = {}
    used_handles: set[str] = set()
    for row in author_rows:
        handle = slugify(row["name"])
        base_handle, n = handle, 2
        while handle in used_handles:
            handle, n = f"{base_handle}-{n}", n + 1
        used_handles.add(handle)
        user = User(
            handle=handle,
            display_name=row["name"],
            affiliation=row["affiliation"],
            web_url=row["web_url"],
        )
        db.add(user)
        users_by_author_id[row["author_id"]] = user
        users_by_name[row["name"]] = user
    import_user = User(handle=PROTOTYPE_IMPORT_HANDLE, display_name="Prototype import")
    db.add(import_user)
    db.flush()
    print(f"Users: {len(author_rows)} authors + 1 import user")

    # ------------------------------------------------------------- lookups
    placeholders = ",".join("?" * len(MIGRATED_SLUGS))
    old_collections = old.execute(
        f"SELECT * FROM collections WHERE slug IN ({placeholders}) ORDER BY year",
        MIGRATED_SLUGS,
    ).fetchall()

    categories_by_term: dict[str, list[str]] = defaultdict(list)
    for row in old.execute(
        """SELECT tc.term_id, c.name FROM term_categories tc
           JOIN categories c ON c.category_id = tc.category_id ORDER BY c.name"""
    ):
        categories_by_term[row["term_id"]].append(row["name"])

    part_code_by_id = {
        row["part_id"]: row["code"] for row in old.execute("SELECT part_id, code FROM parts")
    }

    variants_by_term: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in old.execute(
        "SELECT term_id, variant_text, variant_type FROM variants ORDER BY variant_text"
    ):
        variants_by_term[row["term_id"]].append(row)

    sections_by_term: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in old.execute("SELECT * FROM term_sections"):
        sections_by_term[row["term_id"]].append(row)

    authors_by_section: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in old.execute(
        """SELECT tsa.section_id, a.name, a.affiliation, a.web_url
           FROM term_section_authors tsa
           JOIN authors a ON a.author_id = tsa.author_id
           ORDER BY tsa.author_order"""
    ):
        authors_by_section[row["section_id"]].append(row)

    # ------------------------------------------------- collections + terms
    term_map: dict[str, dict] = {}  # old term_id → {concept_id, version_id, slug, form}
    per_collection: dict[str, int] = {}
    annotation_counts: dict[str, int] = defaultdict(int)
    processed = 0

    for old_coll in old_collections:
        licence = None
        if old_coll["license"]:
            licence = {"label": old_coll["license"]}
            if old_coll["license_url"]:
                licence["url"] = old_coll["license_url"]
        collection = Collection(
            slug=old_coll["slug"],
            name=old_coll["name"],
            description=old_coll["description"],
            year=old_coll["year"],
            licence=licence,
            authoritative=old_coll["slug"].startswith("transmodel"),
        )
        db.add(collection)
        db.flush()

        terms = old.execute(
            "SELECT * FROM terms WHERE collection_id = ? ORDER BY canonical_form, term_id",
            (old_coll["collection_id"],),
        ).fetchall()

        for term in terms:
            tags = list(categories_by_term.get(term["term_id"], []))
            if term["part_id"] and term["part_id"] in part_code_by_id:
                tags.append(f"part:{part_code_by_id[term['part_id']]}")

            # Sections → concatenated definition + stand-off annotations.
            section_annotations: list[tuple[int, int, sqlite3.Row]] = []
            sections = sorted(
                sections_by_term.get(term["term_id"], []),
                key=lambda s: section_sort_key(s["section_number"]),
            )
            if sections:
                pieces: list[str] = []
                pos = 0
                for sec in sections:
                    content = sec["content"].strip()
                    if pieces:
                        pos += 2  # the "\n\n" separator
                    section_annotations.append((pos, pos + len(content), sec))
                    pieces.append(content)
                    pos += len(content)
                definition = "\n\n".join(pieces)
            else:
                definition = term["definition"] or ""

            creator = users_by_name.get(term["author_name"] or "", import_user)
            provenance = {
                "kind": "import",
                "source": "prototype",
                "collection": old_coll["slug"],
                "original_created_at": term["created_at"],
                "confidence": term["confidence_score"],
            }
            _concept, version, _branch = graph.create_concept(
                db,
                collection_id=collection.id,
                canonical_form=term["canonical_form"],
                language=term["language"],
                definition_md=definition,
                status=STATUS_MAP.get(term["status"], "draft"),
                tags=tags,
                note=term["notes"] or f"Importerad från prototypens {old_coll['name']}",
                provenance=provenance,
                created_by=creator.id,
                created_at=datetime(old_coll["year"], 3, 1),
            )

            for start, end, sec in section_annotations:
                db.add(
                    Annotation(
                        version_id=version.id,
                        attr_type="section",
                        start=start,
                        end=end,
                        quote=version.definition_md[start : start + 60],
                        value={"number": sec["section_number"], "title": sec["section_title"]},
                    )
                )
                annotation_counts["section"] += 1
                for author in authors_by_section.get(sec["section_id"], []):
                    db.add(
                        Annotation(
                            version_id=version.id,
                            attr_type="author",
                            start=start,
                            end=end,
                            value={
                                "name": author["name"],
                                "affiliation": author["affiliation"],
                                "web_url": author["web_url"],
                            },
                        )
                    )
                    annotation_counts["author"] += 1

            for variant in variants_by_term.get(term["term_id"], []):
                db.add(
                    Annotation(
                        version_id=version.id,
                        attr_type="variant",
                        start=0,
                        end=0,
                        value={"form": variant["variant_text"], "kind": variant["variant_type"]},
                    )
                )
                annotation_counts["variant"] += 1

            if term["confidence_score"]:
                db.add(
                    Annotation(
                        version_id=version.id,
                        attr_type="confidence",
                        start=0,
                        end=0,
                        value={"score": term["confidence_score"]},
                    )
                )
                annotation_counts["confidence"] += 1

            term_map[term["term_id"]] = {
                "concept_id": version.concept_id,
                "version_id": version.id,
                "slug": old_coll["slug"],
                "collection_id": old_coll["collection_id"],
                "form": term["canonical_form"],
            }
            db.flush()
            processed += 1
            if processed % 200 == 0:
                db.commit()

        per_collection[old_coll["slug"]] = len(terms)
        db.commit()
        print(f"  {old_coll['slug']}: {len(terms)} terms")

    # -------------------------------------------------- translation edges
    translation_edges = 0
    seen_pairs: set[tuple[str, str]] = set()
    for row in old.execute("SELECT * FROM translations"):
        sv = term_map.get(row["term_id_sv"])
        en = term_map.get(row["term_id_en"])
        if not sv or not en:
            continue
        pair = (en["version_id"], sv["version_id"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        db.add(
            VersionEdge(
                child_id=en["version_id"],
                parent_id=sv["version_id"],
                edge_type="translated_from",
                note=f"Migrerad översättning ({row['translation_type']})",
            )
        )
        translation_edges += 1
    db.commit()

    # ------------------------------------------------------------ relations
    relation_count = 0
    skipped_relations = 0
    for row in old.execute("SELECT * FROM relations"):
        rel_type = RELATION_MAP.get(row["relation_type"])
        src = term_map.get(row["from_term_id"])
        dst = term_map.get(row["to_term_id"])
        if not rel_type or not src or not dst:
            skipped_relations += 1
            continue
        db.add(
            ConceptRelation(
                relation_type=rel_type,
                from_concept_id=src["concept_id"],
                to_concept_id=dst["concept_id"],
                note=row["notes"],
                provenance={"kind": "import", "source": "prototype"},
            )
        )
        relation_count += 1

    # ------------------------------------------------------ cross-references
    form_index: dict[tuple[str, str], str] = {}
    for info in term_map.values():
        key = (info["collection_id"], info["form"].lower())
        form_index.setdefault(key, info["concept_id"])

    crossref_count = 0
    unresolved: list[tuple[str, str]] = []
    for row in old.execute(
        "SELECT term_id, referenced_term FROM term_cross_references ORDER BY id"
    ):
        src = term_map.get(row["term_id"])
        if not src:
            continue
        target = form_index.get((src["collection_id"], row["referenced_term"].strip().lower()))
        if target is None:
            unresolved.append((src["form"], row["referenced_term"]))
            continue
        db.add(
            ConceptRelation(
                relation_type="related_to",
                from_concept_id=src["concept_id"],
                to_concept_id=target,
                note="Korsreferens från prototypen",
                provenance={"kind": "import", "source": "prototype"},
            )
        )
        crossref_count += 1

    # --------------------------------------------------------- disambiguation
    disambiguation_count = 0
    groups = old.execute("SELECT * FROM disambiguation_groups").fetchall()
    for group in groups:
        members = [
            (row["disambiguation_order"], term_map[row["term_id"]])
            for row in old.execute(
                """SELECT term_id, disambiguation_order FROM term_disambiguations
                   WHERE group_id = ? ORDER BY disambiguation_order""",
                (group["group_id"],),
            )
            if row["term_id"] in term_map
        ]
        if len(members) < 2:
            continue
        for (_o1, first), (order2, second) in zip(members, members[1:], strict=False):
            db.add(
                ConceptRelation(
                    relation_type="related_to",
                    from_concept_id=first["concept_id"],
                    to_concept_id=second["concept_id"],
                    note=(
                        f"Särskiljning: '{group['canonical_form']}' "
                        f"({len(members)} betydelser, ordning {order2})"
                    ),
                    provenance={"kind": "import", "source": "prototype"},
                )
            )
            disambiguation_count += 1
    db.commit()

    # --------------------------------------------------------------- summary
    print("\n=== Migration summary ===")
    total_terms = 0
    for slug, count in per_collection.items():
        print(f"  {slug}: {count} concepts")
        total_terms += count
    print(f"  TOTAL concepts/versions: {total_terms}")
    print(f"  Users: {len(author_rows)} authors + 1 import user")
    print(f"  Annotations: {dict(annotation_counts)} (total {sum(annotation_counts.values())})")
    print(f"  Translation edges: {translation_edges}")
    print(
        f"  Relations: {relation_count} migrated, {crossref_count} cross-references, "
        f"{disambiguation_count} disambiguation pairs "
        f"(total {relation_count + crossref_count + disambiguation_count}); "
        f"{skipped_relations} relations skipped (outside migrated collections)"
    )
    print(f"  Unresolved cross-references: {len(unresolved)}")
    for form, ref in unresolved:
        print(f"    '{form}' → '{ref}'")
    db.close()
    old.close()


if __name__ == "__main__":
    main()
