"""Incremental v1 → NG import of additional collections (2026-08).

Unlike migrate_from_prototype.py (which DROPS and rebuilds the whole NG
schema), this script adds new collections into the EXISTING NG database
without touching anything else. Same semantic translation:

  Term        → Concept + one initial Version (dated to the collection's
                publication year; real timestamps in provenance)
  Variant     → 'variant' annotations
  confidence  → 'confidence' annotation
  categories/parts → version tags (category names + part:<code>)
  v1 relations within the imported collections
              → ConceptRelations (see_also/related → related_to, broader,
                narrower), er:* notes preserved
  v1 mapping relations (notes 'map:<slug>->transmodel|type=…')
              → ConceptRelations to the EXISTING NG Transmodel concepts,
                resolved via legacy_ids; type=exact → exact_match,
                type=close → close_match, type=related → related_to
  'er:attributes=<json>' note segments → 'er_attributes' annotation
                (kept out of the human-facing version note)

Also inserts legacy_ids rows for the new concepts, so later passes
(e.g. scripts/import_v1_taxonomies.py) resolve them.

Run categories/parts afterwards:
    uv run python scripts/import_v1_taxonomies.py

Usage (from server/):
    uv run python scripts/import_v1_collections_incremental.py [--dry-run] [--replace] [slugs…]
Default slugs: noptis-2020 nordic-netex-profile-2025 suti-2025
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Annotation,
    Collection,
    ConceptRelation,
    LegacyId,
    User,
)

DEFAULT_SLUGS = ["noptis-2020", "nordic-netex-profile-2025", "suti-2025"]
TRANSMODEL_SLUG = "transmodel-2021"
IMPORT_HANDLE = "prototype-import"

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
MAPPING_TYPE = {"exact": "exact_match", "close": "close_match", "related": "related_to"}

# Bilingual short descriptions for the Samlingar cards (locales layer).
LOCALES = {
    "noptis-2020": {
        "sv": {
            "short_description": "Begrepp ur NOPTIS gränssnittsspecifikationer (DII, DOI, ROI, "
            "RII, VSI m.fl.) – den nordiska realtidsstandarden, baserad på "
            "en tidig Transmodel-version."
        },
        "en": {
            "short_description": "Concepts from the NOPTIS interface specifications (DII, DOI, "
            "ROI, RII, VSI et al.) – the Nordic real-time standard, based "
            "on an early Transmodel version."
        },
    },
    "nordic-netex-profile-2025": {
        "sv": {
            "short_description": "Element och relationer i den nordiska NeTEx-profilen enligt "
            "Enturs dokumentation – komplett ER-underlag med arv, innehåll "
            "och referenser."
        },
        "en": {
            "short_description": "Elements and relations of the Nordic NeTEx Profile per Entur's "
            "documentation – complete ER basis with inheritance, "
            "containment and references."
        },
    },
    "suti-2025": {
        "sv": {
            "short_description": "Begrepp ur SUTI-standarden för informationsutbyte inom "
            "anropsstyrd trafik: meddelandetyper, informationsobjekt och "
            "domänbegrepp."
        },
        "en": {
            "short_description": "Concepts from the SUTI standard for demand-responsive "
            "transport data exchange: message types, information objects "
            "and domain concepts."
        },
    },
}


def open_old_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def split_note(raw: str | None) -> tuple[str | None, dict | None]:
    """Separate 'er:attributes=<json>' from the human-facing note."""
    if not raw:
        return None, None
    keep, attrs = [], None
    for seg in raw.split(" | "):
        if seg.startswith("er:attributes="):
            try:
                attrs = json.loads(seg[len("er:attributes=") :])
            except json.JSONDecodeError:
                keep.append(seg)
        else:
            keep.append(seg)
    return (" | ".join(keep) or None), attrs


def wipe_collection(db, slug: str) -> None:
    row = db.execute(text("SELECT id FROM collections WHERE slug = :s"), {"s": slug}).fetchone()
    if not row:
        return
    cid = row[0]
    p = {"cid": cid}
    concepts = "SELECT id FROM concepts WHERE collection_id = :cid"
    versions = f"SELECT id FROM versions WHERE concept_id IN ({concepts})"
    for stmt in [
        f"DELETE FROM concept_relations WHERE from_concept_id IN ({concepts}) OR to_concept_id IN "
        f"({concepts})",
        f"DELETE FROM version_edges WHERE child_id IN ({versions}) OR parent_id IN ({versions})",
        f"DELETE FROM annotations WHERE version_id IN ({versions})",
        f"DELETE FROM endorsements WHERE version_id IN ({versions})",
        f"DELETE FROM list_items WHERE version_id IN ({versions})",
        f"DELETE FROM legacy_ids WHERE concept_id IN ({concepts})",
        f"DELETE FROM concept_taxonomy_values WHERE concept_id IN ({concepts})",
        "DELETE FROM taxonomy_values WHERE taxonomy_id IN (SELECT id FROM taxonomies WHERE "
        "collection_id = :cid)",
        "DELETE FROM taxonomies WHERE collection_id = :cid",
        f"UPDATE branches SET head_version_id = NULL WHERE concept_id IN ({concepts})",
        f"DELETE FROM versions WHERE concept_id IN ({concepts})",
        f"DELETE FROM branches WHERE concept_id IN ({concepts})",
        "DELETE FROM concepts WHERE collection_id = :cid",
        "DELETE FROM collections WHERE id = :cid",
    ]:
        db.execute(text(stmt), p)
    db.commit()
    print(f"  wiped existing NG collection '{slug}'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="*", default=None)
    # No built-in path: the v1 database is named explicitly or via PROTOTYPE_DB.
    parser.add_argument("--old-db", default=os.environ.get("PROTOTYPE_DB") or None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not args.old_db:
        parser.error("--old-db is required (or set PROTOTYPE_DB) — the v1 database path")
    slugs = args.slugs or DEFAULT_SLUGS

    old = open_old_db(args.old_db)
    db = SessionLocal()

    import_user = db.query(User).filter(User.handle == IMPORT_HANDLE).first()
    if import_user is None:
        import_user = User(handle=IMPORT_HANDLE, display_name="Prototype import")
        db.add(import_user)
        db.flush()

    legacy = {r[0]: r[1] for r in db.execute(text("SELECT legacy_id, concept_id FROM legacy_ids"))}

    # v1 lookups
    categories_by_term: dict[str, list[str]] = defaultdict(list)
    for row in old.execute(
        """SELECT tc.term_id, c.name FROM term_categories tc
           JOIN categories c ON c.category_id = tc.category_id ORDER BY c.name"""
    ):
        categories_by_term[row["term_id"]].append(row["name"])
    part_code_by_id = {
        r["part_id"]: r["code"] for r in old.execute("SELECT part_id, code FROM parts")
    }
    variants_by_term: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in old.execute("SELECT term_id, variant_text, variant_type FROM variants"):
        variants_by_term[row["term_id"]].append(row)

    term_map: dict[str, dict] = {}
    stats = {
        "concepts": 0,
        "internal_relations": 0,
        "mapping_relations": 0,
        "variant_ann": 0,
        "attr_ann": 0,
        "skipped_mapping": 0,
    }

    for slug in slugs:
        old_coll = old.execute("SELECT * FROM collections WHERE slug = ?", (slug,)).fetchone()
        if old_coll is None:
            print(f"ERROR: '{slug}' not found in v1 database")
            sys.exit(1)
        existing = db.query(Collection).filter(Collection.slug == slug).first()
        if existing:
            if not args.replace:
                print(f"ERROR: '{slug}' already exists in NG. Use --replace.")
                sys.exit(1)
            if not args.dry_run:
                wipe_collection(db, slug)

        terms = old.execute(
            "SELECT * FROM terms WHERE collection_id = ? ORDER BY canonical_form, term_id",
            (old_coll["collection_id"],),
        ).fetchall()
        print(f"{slug}: {len(terms)} v1 terms")
        if args.dry_run:
            continue

        licence = {"label": old_coll["license"]} if old_coll["license"] else None
        if licence and old_coll["license_url"]:
            licence["url"] = old_coll["license_url"]
        loc = LOCALES.get(slug)
        collection = Collection(
            slug=slug,
            name=old_coll["name"],
            description=old_coll["description"],
            year=old_coll["year"],
            licence=licence,
            source_url=old_coll["source_url"],
            credits=old_coll["credits"],
            visibility="public",
            edit_policy="org",
            is_locked=True,
            locales={lang: {"name": old_coll["name"], **fields} for lang, fields in loc.items()}
            if loc
            else None,
        )
        db.add(collection)
        db.flush()

        version_date = datetime(old_coll["year"] or 2025, 3, 1)
        for term in terms:
            tags = list(categories_by_term.get(term["term_id"], []))
            if term["part_id"] and term["part_id"] in part_code_by_id:
                tags.append(f"part:{part_code_by_id[term['part_id']]}")
            note, er_attrs = split_note(term["notes"])
            provenance = {
                "kind": "import",
                "source": "v1-prototype",
                "collection": slug,
                "original_created_at": term["created_at"],
                "confidence": term["confidence_score"],
            }
            _concept, version, _branch = graph.create_concept(
                db,
                collection_id=collection.id,
                canonical_form=term["canonical_form"],
                language=term["language"],
                definition_md=term["definition"] or "",
                status=STATUS_MAP.get(term["status"], "draft"),
                tags=tags,
                note=note or f"Importerad från {old_coll['name']}",
                provenance=provenance,
                created_by=import_user.id,
                created_at=version_date,
            )
            if er_attrs is not None:
                db.add(
                    Annotation(
                        version_id=version.id,
                        attr_type="er_attributes",
                        start=0,
                        end=0,
                        value={"attributes": er_attrs},
                    )
                )
                stats["attr_ann"] += 1
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
                stats["variant_ann"] += 1
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
            db.add(LegacyId(legacy_id=term["term_id"], concept_id=version.concept_id))
            term_map[term["term_id"]] = {"concept_id": version.concept_id}
            stats["concepts"] += 1
            if stats["concepts"] % 200 == 0:
                db.commit()
        db.commit()

    if args.dry_run:
        print("(dry-run: no NG changes)")
        return

    # ---- relations: internal + cross-collection mappings to Transmodel ----
    coll_ids = tuple(
        r["collection_id"]
        for r in old.execute(
            f"SELECT collection_id FROM collections WHERE slug IN ({','.join('?' * len(slugs))})",
            slugs,
        )
    )
    q = f"""SELECT r.* FROM relations r JOIN terms t ON t.term_id = r.from_term_id
            WHERE t.collection_id IN ({",".join("?" * len(coll_ids))})"""
    for row in old.execute(q, coll_ids):
        src = term_map.get(row["from_term_id"])
        if not src:
            continue
        notes = row["notes"] or ""
        if notes.startswith("map:"):
            # cross-collection mapping to Transmodel — resolve via legacy_ids
            dst_concept = legacy.get(row["to_term_id"])
            if not dst_concept:
                stats["skipped_mapping"] += 1
                continue
            mtype = "related_to"
            for seg in notes.split("|"):
                if seg.startswith("type="):
                    mtype = MAPPING_TYPE.get(seg[5:], "related_to")
            db.add(
                ConceptRelation(
                    relation_type=mtype,
                    from_concept_id=src["concept_id"],
                    to_concept_id=dst_concept,
                    note=notes,
                    provenance={"kind": "import", "source": "v1-prototype"},
                    created_by=import_user.id,
                )
            )
            stats["mapping_relations"] += 1
        else:
            dst = term_map.get(row["to_term_id"])
            rel_type = RELATION_MAP.get(row["relation_type"])
            if not dst or not rel_type:
                continue
            db.add(
                ConceptRelation(
                    relation_type=rel_type,
                    from_concept_id=src["concept_id"],
                    to_concept_id=dst["concept_id"],
                    note=row["notes"],
                    provenance={"kind": "import", "source": "v1-prototype"},
                    created_by=import_user.id,
                )
            )
            stats["internal_relations"] += 1
    db.commit()

    print("\n=== Incremental import summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("\nNext: uv run python scripts/import_v1_taxonomies.py   (categories/parts)")
    db.close()
    old.close()


if __name__ == "__main__":
    main()
