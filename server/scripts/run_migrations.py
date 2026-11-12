"""Run pending NG migrations in order (container startup + manual use).

Migrations are the idempotent scripts/migrate_NNN_*.py files. This runner
adds bookkeeping so environments cannot drift: a `schema_migrations` table
records what has been applied, and only unapplied scripts run, in numeric
order. Any failure stops the run with a non-zero exit (the container then
fails to start, which is the point).

Migrations 006/007 backfill from the v1 prototype database; they run only
when PROTOTYPE_DB points at an existing file, otherwise they are skipped
(and left pending). Use --mark to record them in environments where their
data already exists.

Usage:
    python scripts/run_migrations.py                 # apply pending
    python scripts/run_migrations.py --status        # list applied/pending
    python scripts/run_migrations.py --baseline      # mark ALL as applied, run nothing
    python scripts/run_migrations.py --mark migrate_006_legacy_ids ...
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

NAME_RE = re.compile(r"^(migrate_(\d{3})_[a-z0-9_]+)\.py$")
NEEDS_PROTOTYPE = {"migrate_006_legacy_ids", "migrate_007_collection_details"}


def discover() -> list[tuple[int, str, Path]]:
    found = []
    for p in SCRIPTS.glob("migrate_*.py"):
        m = NAME_RE.match(p.name)
        if m:
            found.append((int(m.group(2)), m.group(1), p))
    return sorted(found)


def ng_db_path() -> Path:
    from app.db import engine  # DATABASE_URL-driven, same as the app

    if engine.url.get_backend_name() != "sqlite":
        raise SystemExit("run_migrations.py currently supports the SQLite backend only")
    return Path(engine.url.database)


def ensure_schema() -> None:
    from app.db import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)  # new tables; no-op for existing ones


def ledger(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TEXT NOT NULL, note TEXT)"
    )
    con.commit()
    return con


def mark(con: sqlite3.Connection, name: str, note: str) -> None:
    con.execute(
        "INSERT OR IGNORE INTO schema_migrations (name, applied_at, note) VALUES (?, ?, ?)",
        (name, datetime.now(UTC).isoformat(timespec="seconds"), note),
    )
    con.commit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--mark", nargs="*", default=None)
    args = ap.parse_args()

    db = ng_db_path()
    if not db.exists() and not args.status:
        db.parent.mkdir(parents=True, exist_ok=True)
    ensure_schema()
    con = ledger(db)
    applied = {r[0] for r in con.execute("SELECT name FROM schema_migrations")}
    migrations = discover()
    prototype = os.environ.get("PROTOTYPE_DB")
    have_prototype = bool(prototype) and Path(prototype).exists()

    if args.status:
        for _n, name, _p in migrations:
            print(f"  {'applied' if name in applied else 'PENDING'}  {name}")
        return
    if args.baseline:
        for _n, name, _p in migrations:
            mark(con, name, "baseline (marked without running)")
        print(f"baseline: {len(migrations)} migrations marked as applied on {db}")
        return
    if args.mark is not None:
        known = {n for _, n, _ in migrations}
        for name in args.mark:
            if name not in known:
                raise SystemExit(f"unknown migration: {name}")
            mark(con, name, "marked manually (data already present)")
            print(f"marked {name}")
        return

    print(f"run_migrations: {db}")
    ran = skipped = 0
    for _n, name, path in migrations:
        if name in applied:
            continue
        cmd = [sys.executable, str(path), str(db)]
        env = dict(os.environ)
        if name in NEEDS_PROTOTYPE:
            if not have_prototype:
                print(f"  ~ {name}: skipped (PROTOTYPE_DB not available) - still pending")
                skipped += 1
                continue
            env["PROTOTYPE_DB"] = prototype
            if name == "migrate_007_collection_details":
                cmd.append(prototype)
        print(f"  > {name}")
        res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        tail = "\n".join((res.stdout or "").strip().splitlines()[-3:])
        if tail:
            print("    " + tail.replace("\n", "\n    "))
        if res.returncode != 0:
            print(res.stderr, file=sys.stderr)
            raise SystemExit(f"migration {name} FAILED (exit {res.returncode}) - aborting")
        mark(con, name, "applied by run_migrations.py")
        ran += 1
    remaining = len(migrations) - len(applied) - ran - skipped
    print(
        f"run_migrations: {ran} applied, {skipped} skipped, {remaining} remaining, "
        f"{len(applied)} previously applied"
    )


if __name__ == "__main__":
    main()
