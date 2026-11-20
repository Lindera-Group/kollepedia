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


def _glossary_db(tmp_path: Path, concepts: list[tuple[str, str, str]]) -> Path:
    """A database with just the tables migration 019 reads and writes;
    `concepts` is (concept id, collection slug, head canonical form)."""
    path = tmp_path / "kollepedia.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE collections (id TEXT PRIMARY KEY, slug TEXT NOT NULL);
        CREATE TABLE concepts (id TEXT PRIMARY KEY, collection_id TEXT NOT NULL);
        CREATE TABLE branches (id TEXT PRIMARY KEY, concept_id TEXT NOT NULL,
                               name TEXT NOT NULL, head_version_id TEXT);
        CREATE TABLE versions (id TEXT PRIMARY KEY, concept_id TEXT NOT NULL,
                               canonical_form TEXT NOT NULL, language TEXT NOT NULL);
        CREATE TABLE legacy_ids (legacy_id TEXT PRIMARY KEY, concept_id TEXT NOT NULL);
        """
    )
    for slug in sorted({slug for _, slug, _ in concepts}):
        con.execute("INSERT INTO collections VALUES (?, ?)", (f"col-{slug}", slug))
    for cid, slug, form in concepts:
        con.execute("INSERT INTO concepts VALUES (?, ?)", (cid, f"col-{slug}"))
        # An older version with another spelling: only the head decides.
        head = f"v1-{cid}"
        con.execute("INSERT INTO versions VALUES (?, ?, ?, 'sv')", (f"v0-{cid}", cid, "Äldre"))
        con.execute("INSERT INTO versions VALUES (?, ?, ?, 'sv')", (head, cid, form))
        con.execute("INSERT INTO branches VALUES (?, ?, 'main', ?)", (f"b-{cid}", cid, head))
    con.commit()
    con.close()
    return path


def _aliases(path: Path) -> dict[str, str]:
    con = sqlite3.connect(path)
    try:
        return dict(con.execute("SELECT legacy_id, concept_id FROM legacy_ids"))
    finally:
        con.close()


def test_migration_019_aliases_the_dead_link_to_the_block_entry(tmp_path: Path) -> None:
    mig = _load("migrate_019_fordonspass_alias")
    path = _glossary_db(
        tmp_path,
        [
            ("block", mig.SLUG, mig.TERM),
            # The "Se vagnomlopp." stub and a namesake elsewhere are not the target.
            ("stub", mig.SLUG, "Fordonspass"),
            ("elsewhere", "nomenklatur-2024", mig.TERM),
        ],
    )

    assert mig.migrate(path) == {"targets": 1, "created": 1}
    assert _aliases(path) == {mig.LEGACY_ID: "block"}

    # Second run: the alias is there, nothing changes.
    assert mig.migrate(path) == {"targets": 1, "created": 0}
    assert _aliases(path) == {mig.LEGACY_ID: "block"}


def test_migration_019_is_a_no_op_without_exactly_one_target(tmp_path: Path) -> None:
    mig = _load("migrate_019_fordonspass_alias")

    absent = _glossary_db(tmp_path, [("stub", mig.SLUG, "Fordonspass")])
    assert mig.migrate(absent) == {"targets": 0, "created": 0}
    assert _aliases(absent) == {}

    (tmp_path / "two").mkdir()
    ambiguous = _glossary_db(
        tmp_path / "two", [("a", mig.SLUG, mig.TERM), ("b", mig.SLUG, mig.TERM)]
    )
    assert mig.migrate(ambiguous) == {"targets": 2, "created": 0}
    assert _aliases(ambiguous) == {}
