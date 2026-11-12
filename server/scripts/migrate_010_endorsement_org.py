"""Migration 010 — endorsement rework: the org→version flag model.

"Fastställd" is no longer a version STATUS — it is an organisation's
withdrawable flag on one specific version (endorsements.organisation_id).
Idempotent, ALTER-based — never drops anything.

1. endorsements.organisation_id  VARCHAR(36) NULL — the endorsing org.
   Historical rows keep NULL and display their free-text `body`.
2. Link historical endorsements to organisations where `body` exactly
   matches an organisation name or slug.
3. versions.status 'endorsed' → 'proposed' — the status vocabulary is now
   draft | proposed | deprecated | superseded (the endorsement records
   carry the "fastställd" semantics from here on).

Run:  uv run python scripts/migrate_010_endorsement_org.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "endorsements_linked": 0, "statuses_converted": 0}

    con = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in con.execute("PRAGMA table_info(endorsements)")}
        if "organisation_id" in existing:
            print("  = endorsements.organisation_id already present — skipped")
        else:
            con.execute("ALTER TABLE endorsements ADD COLUMN organisation_id VARCHAR(36)")
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_endorsements_organisation_id "
                "ON endorsements (organisation_id)"
            )
            counts["columns_added"] += 1
            print("  + endorsements.organisation_id added")

        cur = con.execute(
            """
            UPDATE endorsements SET organisation_id = (
              SELECT o.id FROM organisations o
              WHERE o.name = endorsements.body OR o.slug = endorsements.body
            )
            WHERE organisation_id IS NULL
              AND EXISTS (
                SELECT 1 FROM organisations o
                WHERE o.name = endorsements.body OR o.slug = endorsements.body
              )
            """
        )
        counts["endorsements_linked"] = cur.rowcount
        if cur.rowcount:
            print(f"  ~ {cur.rowcount} historical endorsement(s) linked by body match")

        cur = con.execute("UPDATE versions SET status = 'proposed' WHERE status = 'endorsed'")
        counts["statuses_converted"] = cur.rowcount
        if cur.rowcount:
            print(f"  ~ {cur.rowcount} version(s): status endorsed → proposed")

        con.commit()
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Migrating {db} …")
    result = migrate(db)
    print(f"Done: {result}")
