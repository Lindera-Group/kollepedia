"""Migration 003 — unified authors/users + admin outreach columns.

Author and user are the same entity: the users table already holds the
imported authors (password_hash NULL = unactivated, claimable via
/auth/register). This migration

1. adds the manual-outreach bookkeeping columns to users
   (outreach_status TEXT, outreach_note TEXT, outreach_updated_at DATETIME —
   all NULL; NULL status = not contacted, values used: contacted|opted_out),
2. backfills user linkage into every 'author' annotation: value.name is
   resolved against users.display_name (exact, then case-insensitive);
   missing users are created (slugified handle, affiliation/web_url from the
   annotation) and `user_id` + `handle` are written into the annotation's
   value JSON so the frontend can link bylines to /authors/<handle>.

Idempotent, ALTER-based (safe on the live dev DB — never drops anything).
Run:  uv run python scripts/migrate_003_authors.py [path-to-db]
"""

import json
import re
import sqlite3
import sys
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

COLUMNS: list[tuple[str, str]] = [
    ("outreach_status", "TEXT"),
    ("outreach_note", "TEXT"),
    ("outreach_updated_at", "DATETIME"),
]


def slugify(name: str) -> str:
    """Handle-safe slug: 'Märit Jansson' → 'marit-jansson' (matches auth style)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "forfattare"


def _unique_handle(con: sqlite3.Connection, base: str) -> str:
    handle, n = base, 1
    while con.execute("SELECT 1 FROM users WHERE handle = ?", (handle,)).fetchone():
        n += 1
        handle = f"{base}-{n}"
    return handle


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    con = sqlite3.connect(db_path)
    counts = {"resolved": 0, "created": 0, "unmatched": 0, "already_linked": 0}
    try:
        # -- 1. outreach columns -------------------------------------------
        existing = {row[1] for row in con.execute("PRAGMA table_info(users)")}
        for name, ddl in COLUMNS:
            if name in existing:
                print(f"  = users.{name} already present — skipped")
            else:
                con.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
                print(f"  + users.{name} added ({ddl})")

        # -- 2. backfill user linkage into author annotations --------------
        users_by_id = {
            row[0]: row for row in con.execute("SELECT id, handle, display_name FROM users")
        }
        exact = {row[2]: row for row in users_by_id.values()}
        folded = {row[2].casefold(): row for row in users_by_id.values()}

        rows = con.execute(
            "SELECT id, value FROM annotations WHERE attr_type = 'author'"
        ).fetchall()
        for ann_id, raw in rows:
            try:
                value = json.loads(raw) if raw else {}
            except (TypeError, ValueError):
                value = {}
            name = str(value.get("name") or "").strip()
            if not name:
                counts["unmatched"] += 1
                continue

            linked_id = value.get("user_id")
            if linked_id and linked_id in users_by_id:
                counts["already_linked"] += 1
                if value.get("handle") != users_by_id[linked_id][1]:
                    value["handle"] = users_by_id[linked_id][1]
                    con.execute(
                        "UPDATE annotations SET value = ? WHERE id = ?",
                        (json.dumps(value, ensure_ascii=False), ann_id),
                    )
                continue

            user = exact.get(name) or folded.get(name.casefold())
            if user is None:
                handle = _unique_handle(con, slugify(name))
                user = (str(uuid.uuid4()), handle, name)
                con.execute(
                    "INSERT INTO users (id, handle, display_name, affiliation, web_url,"
                    " is_super_admin, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
                    (
                        user[0],
                        handle,
                        name,
                        value.get("affiliation") or None,
                        value.get("web_url") or None,
                        datetime.now(UTC).isoformat(sep=" "),
                    ),
                )
                users_by_id[user[0]] = user
                exact[name] = user
                folded[name.casefold()] = user
                counts["created"] += 1
            else:
                counts["resolved"] += 1

            value["user_id"] = user[0]
            value["handle"] = user[1]
            con.execute(
                "UPDATE annotations SET value = ? WHERE id = ?",
                (json.dumps(value, ensure_ascii=False), ann_id),
            )
        con.commit()
    finally:
        con.close()

    print(f"\nMigration 003 done: {db_path}")
    print(
        f"  author annotations: {counts['resolved']} resolved to existing users, "
        f"{counts['created']} users created, {counts['already_linked']} already linked, "
        f"{counts['unmatched']} unmatched (no name)"
    )
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
