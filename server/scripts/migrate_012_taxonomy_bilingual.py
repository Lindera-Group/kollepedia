"""Migration 012 — bilingual taxonomy values (name = sv, name_en = en).

Swedish names match v1's established i18n translations (web/src/lib/i18n.js)
for continuity — the vocabulary remains super-admin-mutable.

The taxonomy level is bilingual, unlike free tags. Adds the column and
localises the 14 seeded global categories (they were seeded with English
names in 011 — those move to name_en, Swedish becomes primary). Idempotent.

Run:  uv run python scripts/migrate_012_taxonomy_bilingual.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

SV_BY_EN = {
    "Passenger Services": "Passagerartjänster",
    "Fares & Pricing": "Biljetter & prissättning",
    "Network & Routes": "Nätverk & linjer",
    "Scheduling & Timetables": "Planering & tidtabeller",
    "Operations": "Drift",
    "Management & Statistics": "Ledning & statistik",
    "Technology & Data": "Teknik & data",
    "Environment": "Miljö",
    "Safety & Security": "Säkerhet & trygghet",
    "Transport Modes": "Transportmedel",
    "Urban Mobility": "Urban mobilitet",
    "Demand-Responsive Transport": "Anropsstyrd trafik",
    "Railway Terms": "Järnvägstermer",
    "Governance & Policy": "Styrning & policy",
}


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "values_localised": 0}
    con = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in con.execute("PRAGMA table_info(taxonomy_values)")}
        if "name_en" not in existing:
            con.execute("ALTER TABLE taxonomy_values ADD COLUMN name_en TEXT")
            counts["columns_added"] = 1
            print("  + taxonomy_values.name_en added")
        counts["duplicates_removed"] = 0
        for en, sv in SV_BY_EN.items():
            already = con.execute(
                "SELECT tv.taxonomy_id FROM taxonomy_values tv "
                "JOIN taxonomies t ON t.id = tv.taxonomy_id "
                "WHERE t.scope = 'global' AND t.slug = 'kategorier' AND tv.name = ?",
                (sv,),
            ).fetchall()
            if already:
                # Localised value exists: an English-named twin can only be an
                # accidental re-seed (pre-fix 011). Remove it if nothing uses it.
                cur = con.execute(
                    "DELETE FROM taxonomy_values WHERE name = ? AND name_en IS NULL "
                    "AND taxonomy_id IN (SELECT id FROM taxonomies WHERE scope='global' AND "
                    "slug='kategorier') "
                    "AND id NOT IN (SELECT value_id FROM concept_taxonomy_values)",
                    (en,),
                )
                counts["duplicates_removed"] += cur.rowcount
                continue
            cur = con.execute(
                "UPDATE taxonomy_values SET name = ?, name_en = ? "
                "WHERE name = ? AND name_en IS NULL",
                (sv, en, en),
            )
            counts["values_localised"] += cur.rowcount
        con.commit()
        if counts["duplicates_removed"]:
            print(f"  - {counts['duplicates_removed']} duplicate English value(s) removed")
    finally:
        con.close()
    if counts["values_localised"]:
        print(f"  ~ {counts['values_localised']} value(s) localised (sv primary, en kept)")
    return counts


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Migrating {db} …")
    print(f"Done: {migrate(db)}")
