"""Data migrations that must be safe to run on any environment's database."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _db(tmp_path: Path, rows: list[tuple[str, int]]) -> Path:
    path = tmp_path / "kollepedia.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE collections (slug TEXT PRIMARY KEY, is_locked INTEGER NOT NULL)")
    con.executemany("INSERT INTO collections VALUES (?, ?)", rows)
    con.commit()
    con.close()
    return path


def _locked(path: Path) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        return dict(con.execute("SELECT slug, is_locked FROM collections"))
    finally:
        con.close()


def test_migration_018_locks_samtrafiken_only_and_is_idempotent(tmp_path: Path) -> None:
    mig = _load("migrate_018_lock_samtrafiken")
    path = _db(tmp_path, [(mig.SLUG, 0), ("ordbok-framtidens-resande-2024", 0)])

    assert mig.migrate(path) == {"present": 1, "locked": 1}
    assert _locked(path) == {mig.SLUG: 1, "ordbok-framtidens-resande-2024": 0}

    # Second run: nothing left to change, still succeeds.
    assert mig.migrate(path) == {"present": 1, "locked": 0}
    assert _locked(path)[mig.SLUG] == 1


def test_migration_018_is_a_no_op_without_the_collection(tmp_path: Path) -> None:
    mig = _load("migrate_018_lock_samtrafiken")
    path = _db(tmp_path, [("tidsmaskinen", 1)])

    assert mig.migrate(path) == {"present": 0, "locked": 0}
    assert _locked(path) == {"tidsmaskinen": 1}
