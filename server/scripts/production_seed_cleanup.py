"""Make a copy of the staging database fit to become production.

Run by the one-off workflow `Production cutover` right after the volume
`kollepedia-data` has been seeded from `kollepedia-staging-data`, before the
production server ever starts. A raw copy carries state that must not cross
the trust boundary:

  • live sessions and one-time secrets — refresh tokens, reset tokens,
    activation and e-mail verification tokens, proof-of-work nonces,
    registration-velocity events;
  • the outbox/audit rows of e-mails that were blocked or stored on staging
    (nothing may ever be sent from them in production);
  • the seed owner accounts from scripts/seed_local_orgs.py, which share a
    development password: it is replaced by an unusable random hash (never
    NULL — a NULL hash is a claimable author profile), so they can only be
    reached through a reset link issued by the Ops workflow.

Writes the marker file `.production-scrubbed` next to the database as its
last act; the production deploy refuses to start a volume without it. The
marker never short-circuits a run: every run scrubs.

Idempotent and UPDATE/DELETE-only on the data. Prints what it changed. Usage:

    python scripts/production_seed_cleanup.py [path-to-db]   (default: DATABASE_URL)
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path

from argon2 import PasswordHasher

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.seed_local_orgs import OWNER_ACCOUNTS  # noqa: E402

PURGE_TABLES = (
    "refresh_tokens",
    "reset_tokens",
    "activation_tokens",
    "email_verify_tokens",
    "used_nonces",
    "registration_events",
    "email_messages",
)


MARKER = ".production-scrubbed"


def seed_handles() -> list[str]:
    return sorted(handle for handle, _email, _name in OWNER_ACCOUNTS.values())


def unusable_password_hash() -> str:
    return PasswordHasher().hash(secrets.token_urlsafe(32))


def cleanup(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts: dict[str, int] = {}
    con = sqlite3.connect(db_path)
    try:
        existing = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for table in PURGE_TABLES:
            if table in existing:
                counts[table] = con.execute(f"DELETE FROM {table}").rowcount
        handles = seed_handles()
        placeholders = ",".join("?" for _ in handles)
        # Always replace: a random unusable hash replaced by another random one
        # is harmless, and no marker can ever talk us out of scrubbing.
        counts["seed_passwords_replaced"] = 0
        for (handle,) in con.execute(
            f"SELECT handle FROM users WHERE handle IN ({placeholders})", handles
        ).fetchall():
            con.execute(
                "UPDATE users SET password_hash = ? WHERE handle = ?",
                (unusable_password_hash(), handle),
            )
            counts["seed_passwords_replaced"] += 1
        con.commit()
        # The marker is written last, only after everything above succeeded.
        (db_path.parent / MARKER).write_text(
            "scrubbed for production by scripts/production_seed_cleanup.py\n"
        )
    finally:
        con.close()
    for key, value in counts.items():
        print(f"  · {key}: {value}")
    print(f"Production seed cleanup done: {db_path}")
    return counts


def _default_db() -> Path:
    from app.db import engine

    return Path(engine.url.database)


if __name__ == "__main__":
    cleanup(Path(sys.argv[1]) if len(sys.argv) > 1 else _default_db())
