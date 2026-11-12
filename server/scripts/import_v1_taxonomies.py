"""v1 → NG taxonomy migration (VISION §8.2 mapping decision, plan NG_TAXONOMIES).

Maps the prototype's curated classifications onto NG concepts via legacy_ids:
1. v1 term_categories → assignments in the NG GLOBAL 'kategorier' taxonomy
   (v1 names are English — matched against taxonomy_values.name_en).
   'Seed: *' test categories are skipped.
2. v1 parts (per collection) → an NG collection taxonomy 'parts' (min=max=1)
   with one value per part; terms.part_id → concept assignments.

Idempotent (INSERT OR IGNORE; existing taxonomies/values are reused).
Concepts without a legacy_ids mapping are counted and skipped.

Run:  uv run python scripts/import_v1_taxonomies.py [v1-db] [ng-db]
"""

import sqlite3
import sys
import uuid
from pathlib import Path

_PARENTS = Path(__file__).resolve().parents
ROOT = (
    _PARENTS[3] if len(_PARENTS) > 3 else _PARENTS[-1]
)  # repo root; shallow inside the container
DEFAULT_V1 = ROOT / "data" / "kollepedia.db"
DEFAULT_NG = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"


def migrate(v1_path: Path, ng_path: Path) -> dict[str, int]:
    for path in (v1_path, ng_path):
        if not path.exists():
            raise SystemExit(f"Database not found: {path}")
    v1 = sqlite3.connect(v1_path)
    ng = sqlite3.connect(ng_path)
    counts = {
        "category_assignments": 0,
        "part_taxonomies": 0,
        "part_values": 0,
        "part_assignments": 0,
        "unmapped_terms": 0,
        "unknown_categories": 0,
    }
    try:
        legacy = dict(ng.execute("SELECT legacy_id, concept_id FROM legacy_ids"))
        global_values = {
            (name_en or name).lower(): value_id
            for value_id, name, name_en in ng.execute(
                """SELECT tv.id, tv.name, tv.name_en FROM taxonomy_values tv
                   JOIN taxonomies t ON t.id = tv.taxonomy_id
                   WHERE t.scope = 'global' AND t.slug = 'kategorier'"""
            )
        }

        # 1. Global categories.
        for term_id, cat_name in v1.execute(
            """SELECT tc.term_id, c.name FROM term_categories tc
               JOIN categories c ON c.category_id = tc.category_id"""
        ):
            if cat_name.startswith("Seed:"):
                continue
            concept_id = legacy.get(term_id)
            if concept_id is None:
                counts["unmapped_terms"] += 1
                continue
            value_id = global_values.get(cat_name.lower())
            if value_id is None:
                counts["unknown_categories"] += 1
                continue
            cur = ng.execute(
                "INSERT OR IGNORE INTO concept_taxonomy_values "
                "(concept_id, value_id, added_by, added_at) "
                "VALUES (?, ?, NULL, datetime('now'))",
                (concept_id, value_id),
            )
            counts["category_assignments"] += cur.rowcount

        # 2. Parts per v1 collection → NG collection taxonomy.
        for v1_coll_id, slug in v1.execute(
            "SELECT DISTINCT p.collection_id, c.slug FROM parts p "
            "JOIN collections c ON c.collection_id = p.collection_id"
        ):
            ng_coll = ng.execute("SELECT id FROM collections WHERE slug = ?", (slug,)).fetchone()
            if ng_coll is None:
                print(f"  ! NG-samling saknas för slug '{slug}' — parts hoppas över")
                continue
            tax = ng.execute(
                "SELECT id FROM taxonomies WHERE collection_id = ? AND slug = 'parts'",
                (ng_coll[0],),
            ).fetchone()
            if tax is None:
                tax_id = str(uuid.uuid4())
                ng.execute(
                    "INSERT INTO taxonomies (id, slug, name, description, scope, "
                    "collection_id, min_per_concept, max_per_concept, created_at) "
                    "VALUES (?, 'parts', 'Delar', 'Källstandardens delar (v1-migrering).', "
                    "'collection', ?, 1, 1, datetime('now'))",
                    (tax_id, ng_coll[0]),
                )
                counts["part_taxonomies"] += 1
            else:
                tax_id = tax[0]
            value_by_part: dict[str, str] = {}
            for part_id, _code, name, sort_order in v1.execute(
                "SELECT part_id, code, name, sort_order FROM parts "
                "WHERE collection_id = ? ORDER BY sort_order",
                (v1_coll_id,),
            ):
                row = ng.execute(
                    "SELECT id FROM taxonomy_values WHERE taxonomy_id = ? AND name = ?",
                    (tax_id, name),
                ).fetchone()
                if row is None:
                    value_id = str(uuid.uuid4())
                    ng.execute(
                        "INSERT INTO taxonomy_values "
                        "(id, taxonomy_id, name, name_en, position, created_at) "
                        "VALUES (?, ?, ?, NULL, ?, datetime('now'))",
                        (value_id, tax_id, name, sort_order),
                    )
                    counts["part_values"] += 1
                else:
                    value_id = row[0]
                value_by_part[part_id] = value_id
            for term_id, part_id in v1.execute(
                "SELECT term_id, part_id FROM terms "
                "WHERE part_id IS NOT NULL AND collection_id = ?",
                (v1_coll_id,),
            ):
                concept_id = legacy.get(term_id)
                value_id = value_by_part.get(part_id)
                if concept_id is None or value_id is None:
                    counts["unmapped_terms"] += 1
                    continue
                cur = ng.execute(
                    "INSERT OR IGNORE INTO concept_taxonomy_values "
                    "(concept_id, value_id, added_by, added_at) "
                    "VALUES (?, ?, NULL, datetime('now'))",
                    (concept_id, value_id),
                )
                counts["part_assignments"] += cur.rowcount
        ng.commit()
    finally:
        v1.close()
        ng.close()
    return counts


if __name__ == "__main__":
    v1_db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_V1
    ng_db = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NG
    print(f"v1: {v1_db}\nNG: {ng_db}")
    print(f"Done: {migrate(v1_db, ng_db)}")
