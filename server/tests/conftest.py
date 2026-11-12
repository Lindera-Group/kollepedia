"""Test fixtures: in-memory SQLite + dependency-overridden TestClient.

app/db.py creates a file engine at import time — tests never use it. Instead
we build a StaticPool in-memory engine per test and override get_db, so every
test runs against a fresh, isolated schema.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ratelimit
from app.db import get_db
from app.main import app
from app.models import Base, Collection


@pytest.fixture(autouse=True)
def _rate_limit_isolation(monkeypatch):
    """Rate limits must never couple tests: raise the ceilings sky-high and
    clear the sliding windows before and after each test. The dedicated 429
    test tightens the env again via its own monkeypatch."""
    monkeypatch.setenv("RATE_LIMIT_AUTH", "10000")
    monkeypatch.setenv("RATE_LIMIT_AI", "10000")
    # The X-User dev fallback is off by default (app/deps.py); the suite signs
    # most requests with it, so turn it on. test_night3 covers the off state.
    monkeypatch.setenv("DEV_AUTH", "1")
    # Registration PoW stays ON in tests (the full verify path runs) but at a
    # difficulty a laptop solves in microseconds, without the human fill-time
    # floor, and without the source-velocity cap (TestClient = one IP).
    # The dedicated hardening tests tighten these again individually.
    monkeypatch.setenv("POW_BITS", "8")
    monkeypatch.setenv("POW_MIN_FILL_SECONDS", "0")
    monkeypatch.setenv("REG_VELOCITY_LIMIT", "1000")
    # The AI feature is off by default (server/app/features.py); the suite
    # exercises it, so turn it on. test_features.py covers the dark state.
    monkeypatch.setenv("FEATURE_AI", "1")
    ratelimit.reset()
    yield
    ratelimit.reset()


def solve_pow(client: TestClient) -> dict:
    """Fetch and solve a registration PoW challenge — the JSON `pow` payload
    /auth/register requires. Tests run at POW_BITS=8 (~128 hashes)."""
    from app.pow import solve

    challenge = client.get("/api/v1/auth/challenge").json()
    number = solve(challenge["salt"], challenge["bits"])
    return {**challenge, "number": number}


def register_payload(client: TestClient, **fields) -> dict:
    """A valid /auth/register body: caller's fields + a solved PoW."""
    return {**fields, "pow": solve_pow(client)}


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def client(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # No context manager: the lifespan would create_all against the real file DB.
    # Default dev identity: writes require *some* user (iteration 2); tests that
    # need anonymity override with headers={"X-User": ""}.
    yield TestClient(app, headers={"X-User": "testare"})
    app.dependency_overrides.clear()


@pytest.fixture()
def collection(db) -> Collection:
    coll = Collection(slug="testsamling", name="Testsamling", year=2026)
    db.add(coll)
    db.commit()
    return coll
