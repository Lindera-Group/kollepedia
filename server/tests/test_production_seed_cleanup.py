"""The staging → production copy sheds sessions, one-time secrets, mail rows
and the seed accounts' shared development password."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "production_seed_cleanup", SCRIPTS / "production_seed_cleanup.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _staging_like_db(tmp_path: Path, seed_handle: str) -> Path:
    path = tmp_path / "kollepedia.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE users (handle TEXT PRIMARY KEY, password_hash TEXT);
        CREATE TABLE refresh_tokens (id INTEGER PRIMARY KEY);
        CREATE TABLE reset_tokens (id INTEGER PRIMARY KEY);
        CREATE TABLE used_nonces (id INTEGER PRIMARY KEY);
        CREATE TABLE email_messages (id INTEGER PRIMARY KEY, status TEXT);
        INSERT INTO refresh_tokens VALUES (1), (2);
        INSERT INTO reset_tokens VALUES (1);
        INSERT INTO used_nonces VALUES (1), (2), (3);
        INSERT INTO email_messages VALUES (1, 'blocked'), (2, 'outbox');
        """
    )
    con.execute("INSERT INTO users VALUES (?, 'argon2$dev')", (seed_handle,))
    con.execute("INSERT INTO users VALUES ('jonas-johansson', NULL)")
    con.execute("INSERT INTO users VALUES ('martin', 'argon2$real')")
    con.commit()
    con.close()
    return path


def test_cleanup_purges_state_and_replaces_seed_passwords_only(tmp_path: Path) -> None:
    mod = _load()
    seed = mod.seed_handles()[0]
    path = _staging_like_db(tmp_path, seed)

    counts = mod.cleanup(path)

    assert counts["refresh_tokens"] == 2 and counts["reset_tokens"] == 1
    assert counts["used_nonces"] == 3 and counts["email_messages"] == 2
    assert counts["seed_passwords_replaced"] == 1
    # Tables missing from this schema (activation_tokens …) are simply skipped.
    assert "activation_tokens" not in counts

    con = sqlite3.connect(path)
    rows = dict(con.execute("SELECT handle, password_hash FROM users"))
    con.close()
    # Dev password gone, but NOT NULL: a NULL hash would be claimable via /activate.
    assert rows[seed] != "argon2$dev" and rows[seed] is not None
    assert rows[seed].startswith("$argon2")
    assert rows["martin"] == "argon2$real"  # real accounts untouched
    assert rows["jonas-johansson"] is None  # not a seed account: left as it was
    assert (tmp_path / mod.MARKER).exists()

    # Second run: tables already empty, seed hash replaced again (never the
    # dev hash, never NULL) — a marker never talks the scrub out of running.
    again = mod.cleanup(path)
    assert again["seed_passwords_replaced"] == 1 and again["refresh_tokens"] == 0
    con = sqlite3.connect(path)
    after = dict(con.execute("SELECT handle, password_hash FROM users"))[seed]
    con.close()
    assert after not in (None, "argon2$dev") and after.startswith("$argon2")
