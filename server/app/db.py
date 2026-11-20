"""Database engine and session. DATABASE_URL-driven; SQLite in dev, Postgres-ready."""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'kollepedia.db'}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def _lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


def fold_all_letters(sqlite_engine: Engine) -> None:
    """Make lower() on this SQLite engine fold every letter, not only A–Z.

    SQLite's own lower() leaves Å Ä Ö (and every other letter outside ASCII)
    as they are, so "Ändhållplats" and "ändhållplats" would be two different
    words to every case-insensitive comparison: the search, the duplicate
    check at import, the lookups by e-mail and handle. They all go through
    lower() (`ilike` compiles to it), so replacing it per connection settles
    it in one place. Every SQLite engine the app or its tests query through
    must be passed here."""

    @event.listens_for(sqlite_engine, "connect")
    def _register(dbapi_connection, connection_record):  # noqa: ANN001
        dbapi_connection.create_function("lower", 1, _lower, deterministic=True)


if DATABASE_URL.startswith("sqlite"):
    fold_all_letters(engine)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
