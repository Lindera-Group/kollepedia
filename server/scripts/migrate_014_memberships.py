"""Migration 014 — multi-organisation memberships + ownership + org types.

Membership moves off the users row into org_memberships (many orgs per
user); ownership of at most ONE org per user lives in
organisations.owner_user_id (UNIQUE). Idempotent, ALTER-based — never
drops anything: users.organisation_id/org_role stay physically in place
but are never read again by the application.

1. org_memberships table + partial unique index (one ACTIVE membership per
   user and organisation; ended rows are history).
2. organisations.owner_user_id VARCHAR(36) NULL + UNIQUE index — the
   economic-responsibility anchor ("one owned org per user" is structural).
3. organisations.org_type VARCHAR(40) NULL — commercial | academy |
   industry_association, confirmed by a super admin at approval.
4. admin_events table — audit log for super-admin actions (guardrail G5).
5. Backfill memberships from users.organisation_id/org_role (super admins
   excluded — guardrail G1: a super admin holds no memberships).
6. Backfill owner_user_id = created_by where that user now holds an active
   admin membership of the org.

Run:  uv run python scripts/migrate_014_memberships.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {
        "tables_created": 0,
        "columns_added": 0,
        "memberships_backfilled": 0,
        "owners_backfilled": 0,
    }

    con = sqlite3.connect(db_path)
    try:
        tables = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        if "org_memberships" in tables:
            print("  = org_memberships already present — skipped")
        else:
            con.execute(
                """
                CREATE TABLE org_memberships (
                  id VARCHAR(36) NOT NULL PRIMARY KEY,
                  user_id VARCHAR(36) NOT NULL REFERENCES users (id),
                  organisation_id VARCHAR(36) NOT NULL REFERENCES organisations (id),
                  role VARCHAR(20) NOT NULL DEFAULT 'viewer',
                  kind VARCHAR(20) NOT NULL DEFAULT 'member',
                  is_public BOOLEAN NOT NULL DEFAULT 1,
                  invited_by VARCHAR(36),
                  created_at DATETIME NOT NULL,
                  ended_at DATETIME,
                  CONSTRAINT org_memberships_role_check
                    CHECK (role IN ('admin', 'editor', 'viewer')),
                  CONSTRAINT org_memberships_kind_check
                    CHECK (kind IN ('member', 'guest'))
                )
                """
            )
            counts["tables_created"] += 1
            print("  + org_memberships created")
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_org_memberships_user_id ON org_memberships (user_id)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_org_memberships_organisation_id "
            "ON org_memberships (organisation_id)"
        )
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_membership_active "
            "ON org_memberships (user_id, organisation_id) WHERE ended_at IS NULL"
        )

        org_cols = {row[1] for row in con.execute("PRAGMA table_info(organisations)")}
        if "owner_user_id" in org_cols:
            print("  = organisations.owner_user_id already present — skipped")
        else:
            con.execute("ALTER TABLE organisations ADD COLUMN owner_user_id VARCHAR(36)")
            counts["columns_added"] += 1
            print("  + organisations.owner_user_id added")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_organisations_owner "
            "ON organisations (owner_user_id)"
        )
        if "org_type" in org_cols:
            print("  = organisations.org_type already present — skipped")
        else:
            con.execute("ALTER TABLE organisations ADD COLUMN org_type VARCHAR(40)")
            counts["columns_added"] += 1
            print("  + organisations.org_type added")

        if "admin_events" in tables:
            print("  = admin_events already present — skipped")
        else:
            con.execute(
                """
                CREATE TABLE admin_events (
                  id VARCHAR(36) NOT NULL PRIMARY KEY,
                  actor_id VARCHAR(36) NOT NULL REFERENCES users (id),
                  action VARCHAR(80) NOT NULL,
                  target_type VARCHAR(40) NOT NULL,
                  target_id VARCHAR(36) NOT NULL,
                  note TEXT,
                  created_at DATETIME NOT NULL
                )
                """
            )
            counts["tables_created"] += 1
            print("  + admin_events created")
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_events_actor_id ON admin_events (actor_id)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_admin_events_target_id ON admin_events (target_id)"
        )

        # 5. Backfill memberships from the legacy one-org columns. Super admins
        #    are excluded (G1) and rows already present are left alone.
        user_cols = {row[1] for row in con.execute("PRAGMA table_info(users)")}
        if "organisation_id" in user_cols:
            cur = con.execute(
                """
                INSERT INTO org_memberships
                  (id, user_id, organisation_id, role, kind, is_public,
                   invited_by, created_at, ended_at)
                SELECT
                  lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4'
                    || substr(lower(hex(randomblob(2))), 2) || '-'
                    || substr('89ab', abs(random()) % 4 + 1, 1)
                    || substr(lower(hex(randomblob(2))), 2) || '-'
                    || lower(hex(randomblob(6))),
                  u.id, u.organisation_id, COALESCE(u.org_role, 'viewer'),
                  'member', 1, NULL, datetime('now'), NULL
                FROM users u
                WHERE u.organisation_id IS NOT NULL
                  AND u.is_super_admin = 0
                  AND NOT EXISTS (
                    SELECT 1 FROM org_memberships m
                    WHERE m.user_id = u.id
                      AND m.organisation_id = u.organisation_id
                      AND m.ended_at IS NULL
                  )
                """
            )
            counts["memberships_backfilled"] = cur.rowcount
            if cur.rowcount:
                print(f"  ~ {cur.rowcount} membership(s) backfilled from users")

        # 6. Owner backfill: the creator becomes owner where they hold an
        #    active admin membership and neither side is already claimed.
        cur = con.execute(
            """
            UPDATE organisations SET owner_user_id = created_by
            WHERE owner_user_id IS NULL
              AND created_by IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM org_memberships m
                WHERE m.user_id = organisations.created_by
                  AND m.organisation_id = organisations.id
                  AND m.role = 'admin' AND m.ended_at IS NULL
              )
              AND NOT EXISTS (
                SELECT 1 FROM organisations o2
                WHERE o2.owner_user_id = organisations.created_by
              )
            """
        )
        counts["owners_backfilled"] = cur.rowcount
        if cur.rowcount:
            print(f"  ~ {cur.rowcount} owner(s) backfilled from created_by")

        con.commit()
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Migrating {db} …")
    result = migrate(db)
    print(f"Done: {result}")
