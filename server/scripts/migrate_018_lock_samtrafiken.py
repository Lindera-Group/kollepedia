"""Migration 018 — lock Samtrafiken's glossary (beslut 2026-11-08).

Migration 015 locked the org-less public reference collections. Samtrafikens
begreppslista is the one public reference collection that is org-owned
(Samtrafiken i Sverige AB), so it fell outside that rule and stayed
unlocked when it was published by permission on 2026-09-15. It is a
published-by-permission import, not a living glossary: it must be
read-only like the other reference collections.

Effect of is_locked for an org-owned collection (app/deps.py): direct
writes only for the owning organisation's admins and super admins; every
authenticated user can still contribute through branch proposals.

Idempotent, UPDATE-only (never drops). A database without the collection
(fresh seed) is left untouched and the migration still counts as applied.

Run:  uv run python scripts/migrate_018_lock_samtrafiken.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"
SLUG = "samtrafiken-begreppslista-2024"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"present": 0, "locked": 0}
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT is_locked FROM collections WHERE slug = ?", (SLUG,)).fetchone()
        if row is None:
            print(f"Migration 018: {SLUG} not present in {db_path} — nothing to do")
            return counts
        counts["present"] = 1
        cur = con.execute(
            "UPDATE collections SET is_locked = 1 WHERE slug = ? AND is_locked = 0", (SLUG,)
        )
        counts["locked"] = cur.rowcount
        con.commit()
        print(
            f"Migration 018 done: {db_path}\n"
            f"  · {SLUG}: is_locked {row[0]}→1" + ("" if counts["locked"] else " (already locked)")
        )
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
