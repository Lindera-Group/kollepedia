"""Migration 004 — auth hardening + lock/archive + suspension (iteration 3).

Adds, if missing (idempotent, ALTER-based — never drops anything):

1. users.email        TEXT NULL          (+ unique index ix_users_email)
2. users.is_active    BOOLEAN NOT NULL DEFAULT 1
3. collections.is_locked    BOOLEAN NOT NULL DEFAULT 0
4. collections.is_archived  BOOLEAN NOT NULL DEFAULT 0
5. organisations.is_suspended BOOLEAN NOT NULL DEFAULT 0
6. refresh_tokens + reset_tokens tables (NEW tables → created via the models'
   Base.metadata.create_all, which is a no-op for everything that exists).

Run:  uv run python scripts/migrate_004_hardening.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

# table → [(column, DDL)]
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("email", "TEXT"),
        ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
    ],
    "collections": [
        ("is_locked", "BOOLEAN NOT NULL DEFAULT 0"),
        ("is_archived", "BOOLEAN NOT NULL DEFAULT 0"),
    ],
    "organisations": [
        ("is_suspended", "BOOLEAN NOT NULL DEFAULT 0"),
    ],
}

NEW_TABLES = ("refresh_tokens", "reset_tokens")


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "tables_created": 0}

    con = sqlite3.connect(db_path)
    try:
        # -- 1–5. ALTER ADD COLUMN if missing ------------------------------
        for table, columns in COLUMNS.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns:
                if name in existing:
                    print(f"  = {table}.{name} already present — skipped")
                else:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    counts["columns_added"] += 1
                    print(f"  + {table}.{name} added ({ddl})")
        # unique index for users.email (ALTER cannot add UNIQUE; matches the
        # model's unique+index definition).
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
        con.commit()
    finally:
        con.close()

    # -- 6. new tables via the models (no-op for existing tables) ----------
    from sqlalchemy import create_engine, inspect

    from app.models import Base

    engine = create_engine(f"sqlite:///{db_path}")
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)
    after = set(inspect(engine).get_table_names())
    for table in NEW_TABLES:
        if table in after and table not in before:
            counts["tables_created"] += 1
            print(f"  + table {table} created")
        else:
            print(f"  = table {table} already present — skipped")
    engine.dispose()

    print(f"\nMigration 004 done: {db_path}")
    print(f"  {counts['columns_added']} columns added, {counts['tables_created']} tables created")
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
