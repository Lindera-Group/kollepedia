"""Migration 005 — email, edit policy + collaboration tables (iteration 4).

Adds, if missing (idempotent, ALTER-based — never drops anything):

1. users.email_verified     BOOLEAN NOT NULL DEFAULT 0
2. users.email_verified_at  DATETIME NULL
3. collections.edit_policy  VARCHAR(20) NOT NULL DEFAULT 'anyone'
   — backfilled once: org-owned → 'org', org-less stays 'anyone'.
4. email_messages, email_verify_tokens, change_proposals, comments,
   watches, saved_prompts (NEW tables → created via the models'
   Base.metadata.create_all, which is a no-op for everything that exists).

Run:  uv run python scripts/migrate_005_collab.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

# table → [(column, DDL)]
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("email_verified", "BOOLEAN NOT NULL DEFAULT 0"),
        ("email_verified_at", "DATETIME"),
    ],
    "collections": [
        ("edit_policy", "VARCHAR(20) NOT NULL DEFAULT 'anyone'"),
    ],
}

NEW_TABLES = (
    "email_messages",
    "email_verify_tokens",
    "change_proposals",
    "comments",
    "watches",
    "saved_prompts",
)


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"columns_added": 0, "tables_created": 0, "policies_backfilled": 0}

    con = sqlite3.connect(db_path)
    try:
        # -- 1–3. ALTER ADD COLUMN if missing ------------------------------
        for table, columns in COLUMNS.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, ddl in columns:
                if name in existing:
                    print(f"  = {table}.{name} already present — skipped")
                    continue
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                counts["columns_added"] += 1
                print(f"  + {table}.{name} added ({ddl})")
                if table == "collections" and name == "edit_policy":
                    # One-time backfill (only when the column was just added,
                    # so re-runs never override deliberate policy changes):
                    # org-owned collections keep their night-3 semantics.
                    cursor = con.execute(
                        "UPDATE collections SET edit_policy = 'org' "
                        "WHERE organisation_id IS NOT NULL"
                    )
                    counts["policies_backfilled"] = cursor.rowcount
                    print(
                        f"  ~ collections.edit_policy backfilled: "
                        f"{cursor.rowcount} org-owned → 'org', rest 'anyone'"
                    )
        con.commit()
    finally:
        con.close()

    # -- 4. new tables via the models (no-op for existing tables) ----------
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

    print(f"\nMigration 005 done: {db_path}")
    print(
        f"  {counts['columns_added']} columns added, "
        f"{counts['tables_created']} tables created, "
        f"{counts['policies_backfilled']} edit policies backfilled"
    )
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
