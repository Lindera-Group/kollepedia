"""Migration 002 — auth, organisations and collection visibility (iteration 2).

Idempotent, ALTER-based (safe on the live dev DB — never drops anything):

  users         += password_hash TEXT, is_super_admin BOOL DEFAULT 0,
                   org_role VARCHAR(20)
  organisations += is_approved BOOL DEFAULT 0, created_by VARCHAR(36)
  collections   += visibility VARCHAR(20) DEFAULT 'public', created_by VARCHAR(36)

Also ensures the user 'martin' exists (claimable via /auth/register).

Run:  uv run python scripts/migrate_002_auth.py [path-to-db]
"""

import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("password_hash", "TEXT"),
        ("is_super_admin", "BOOLEAN NOT NULL DEFAULT 0"),
        ("org_role", "VARCHAR(20)"),
    ],
    "organisations": [
        ("is_approved", "BOOLEAN NOT NULL DEFAULT 0"),
        ("created_by", "VARCHAR(36)"),
    ],
    "collections": [
        ("visibility", "VARCHAR(20) NOT NULL DEFAULT 'public'"),
        ("created_by", "VARCHAR(36)"),
    ],
}


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    con = sqlite3.connect(db_path)
    try:
        for table, columns in COLUMNS.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns:
                if name in existing:
                    print(f"  = {table}.{name} already present — skipped")
                else:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    print(f"  + {table}.{name} added ({ddl})")

        row = con.execute("SELECT id, password_hash FROM users WHERE handle = 'martin'").fetchone()
        if row is None:
            con.execute(
                "INSERT INTO users (id, handle, display_name, is_super_admin, created_at)"
                " VALUES (?, 'martin', 'Martin', 0, ?)",
                (str(uuid.uuid4()), datetime.now(UTC).isoformat(sep=" ")),
            )
            print("  + user 'martin' created (no password yet)")
        elif row[1] is None:
            print("  = user 'martin' exists without password")
        else:
            print("  = user 'martin' exists and is already claimed")
        con.commit()
    finally:
        con.close()

    print(f"\nMigration 002 done: {db_path}")
    print(
        "NOTE: 'martin' has no password — claim the identity by registering with "
        "handle 'martin' in the UI (Skapa konto). The first account that sets a "
        "password becomes super admin."
    )


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
