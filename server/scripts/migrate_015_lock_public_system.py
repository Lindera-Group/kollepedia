"""Migration 015 — lock the public system collections (beslut 2026-07-15).

Org-less public collections are the authoritative reference imports (Transmodel,
Kollektivtrafikordboken, Kollepedia 2012, Trafikverkets järnvägstermer,
Tidsmaskinen). Only a super admin can create them (collections.py:
collection_org_required blocks everyone else), so "org-less + public" IS the
"system collection" category. They must not be world-editable.

Idempotent, UPDATE-only (never drops):
  • edit_policy → 'org'  → can_edit_collection falls through to False for
    everyone but a super admin (org-less, non-private, policy not anyone/open).
  • is_locked   → 1      → the lock banner + only super admins are lock-exempt;
    everyone else contributes via branch proposals (branch_exempt).

Together: authoritative sources are read-only except to super admins, who can
still unlock via the collection page's lock toggle.

Run:  uv run python scripts/migrate_015_lock_public_system.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

_WHERE = "visibility = 'public' AND organisation_id IS NULL"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"policy_locked": 0, "edit_locked": 0}
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            f"SELECT slug, edit_policy, is_locked FROM collections WHERE {_WHERE}"
        ).fetchall()
        pol = con.execute(
            f"UPDATE collections SET edit_policy = 'org' WHERE {_WHERE} AND edit_policy != 'org'"
        )
        counts["policy_locked"] = pol.rowcount
        lock = con.execute(
            f"UPDATE collections SET is_locked = 1 WHERE {_WHERE} AND is_locked = 0"
        )
        counts["edit_locked"] = lock.rowcount
        con.commit()
        for slug, policy, locked in rows:
            print(f"  · {slug}: edit_policy {policy}→org, is_locked {locked}→1")
        print(
            f"\nMigration 015 done: {db_path}\n"
            f"  {counts['policy_locked']} policy tightened, "
            f"{counts['edit_locked']} locked"
        )
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
