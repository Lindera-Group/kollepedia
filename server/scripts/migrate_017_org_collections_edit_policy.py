"""Migration 017 - org-owned collections are edited by the owning org only.

Regel (2026-09-15): nobody edits a collection except super admins
and, when the collection has an organisation, that organisation's admins
and editors. can_edit_collection implements this for edit_policy='org';
with 'anyone' every authenticated account that can SEE the collection may
write - for an org_private collection that includes members with the
viewer role. Migration 015 covered the org-less public system collections;
this one covers the org-owned ones (e.g. K2's Ordbok för framtidens resande).

Idempotent, UPDATE-only (never drops):
  organisation_id IS NOT NULL AND edit_policy IN ('anyone','open') -> 'org'

Run:  uv run python scripts/migrate_017_org_collections_edit_policy.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"


def migrate(db: Path) -> int:
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT slug, edit_policy FROM collections "
            "WHERE organisation_id IS NOT NULL AND edit_policy IN ('anyone', 'open')"
        ).fetchall()
        for slug, policy in rows:
            print(f"  {slug}: edit_policy {policy} -> org")
        con.execute(
            "UPDATE collections SET edit_policy = 'org' "
            "WHERE organisation_id IS NOT NULL AND edit_policy IN ('anyone', 'open')"
        )
        con.commit()
        return len(rows)
    finally:
        con.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Migrating {db} ...")
    print(f"Done: {migrate(db)} collection(s) updated")
