"""Migration 013 — DB-enforced one-active-flag-per-org-and-concept (Bengt #6).

Adds endorsements.concept_id (denormalised from the version), backfills it,
and creates the partial unique index that makes the invariant impossible to
race past at the application layer. Idempotent.

Run:  uv run python scripts/migrate_013_endorsement_concept.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "backfilled": 0}
    con = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in con.execute("PRAGMA table_info(endorsements)")}
        if "concept_id" not in existing:
            con.execute("ALTER TABLE endorsements ADD COLUMN concept_id VARCHAR(36)")
            counts["columns_added"] = 1
            print("  + endorsements.concept_id added")
        cur = con.execute(
            """
            UPDATE endorsements SET concept_id = (
              SELECT v.concept_id FROM versions v WHERE v.id = endorsements.version_id
            )
            WHERE concept_id IS NULL
            """
        )
        counts["backfilled"] = cur.rowcount
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_endorsement_active_org_concept "
            "ON endorsements (organisation_id, concept_id) "
            "WHERE withdrawn_at IS NULL AND organisation_id IS NOT NULL"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_endorsements_concept_id ON endorsements (concept_id)"
        )
        con.commit()
    finally:
        con.close()
    if counts["backfilled"]:
        print(f"  ~ {counts['backfilled']} row(s) backfilled")
    return counts


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Migrating {db} …")
    print(f"Done: {migrate(db)}")
