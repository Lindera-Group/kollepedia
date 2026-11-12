"""Migration 008 — account hardening + profile fields (SPAM defence).

Adds, if missing (idempotent, ALTER-based — never drops anything):

1. users.bio            TEXT NULL           (individual profile: short bio)
2. users.review_status  TEXT NOT NULL DEFAULT 'approved'
                        ('approved' | 'pending' | 'rejected' — manual review
                         of suspicious registrations; pending blocks writes)
3. users.review_reason  TEXT NULL           (why the account was flagged)
4. used_nonces + registration_events tables (NEW tables → created via the
   models' Base.metadata.create_all, no-op for everything that exists).
5. collections.edit_policy 'open' → 'anyone' — anonymous users are removed
   from the product entirely; wiki mode without identity is gone. The column
   value migrates so old rows follow the new rule (any signed-in account).

Run:  uv run python scripts/migrate_008_account_hardening.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("bio", "TEXT"),
        ("review_status", "TEXT NOT NULL DEFAULT 'approved'"),
        ("review_reason", "TEXT"),
    ],
}

NEW_TABLES = ("used_nonces", "registration_events")


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "tables_created": 0, "policies_migrated": 0}

    con = sqlite3.connect(db_path)
    try:
        for table, columns in COLUMNS.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns:
                if name in existing:
                    print(f"  = {table}.{name} already present — skipped")
                else:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    counts["columns_added"] += 1
                    print(f"  + {table}.{name} added ({ddl})")

        cursor = con.execute(
            "UPDATE collections SET edit_policy = 'anyone' WHERE edit_policy = 'open'"
        )
        counts["policies_migrated"] = cursor.rowcount
        if cursor.rowcount:
            print(f"  ~ {cursor.rowcount} collection(s) edit_policy open → anyone")
        else:
            print("  = no 'open' edit policies to migrate")
        con.commit()
    finally:
        con.close()

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

    print(f"\nMigration 008 done: {db_path}")
    print(
        f"  {counts['columns_added']} columns added, "
        f"{counts['tables_created']} tables created, "
        f"{counts['policies_migrated']} policies migrated"
    )
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
