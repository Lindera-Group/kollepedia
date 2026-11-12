"""Realtime collab relay (app/realtime.py): y-protocol sync + room admission.

The `ws_client` fixture shares ONE anyio blocking portal across every
websocket session in a test — Starlette's TestClient otherwise spins a fresh
event loop per session, and two collaborators can only meet in the same
in-memory room when their connection handlers run on the same loop. Sharing
the portal by hand (instead of `with TestClient(...)`) also skips the app
lifespan, which would create_all against the real file database.

Rejections are accept-then-close (see app/realtime.py), so they surface here
as WebSocketDisconnect with the application close code on the first receive.
"""

import asyncio
import gc
from contextlib import suppress

import anyio.from_thread
import pytest
from fastapi.testclient import TestClient
from pycrdt import Doc, Text, create_update_message, read_message
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app import realtime
from app.db import get_db
from app.deps import create_token
from app.main import app
from app.models import Collection, Concept, Organisation, OrgMembership, User

YMESSAGE_SYNC = 0
YSYNC_STEP1 = 0
YSYNC_UPDATE = 2


async def _teardown_realtime() -> None:
    """Stop this loop's relay and drop its rooms ON the portal thread —
    pycrdt's Rust subscription objects are unsendable and emit unraisable
    RuntimeErrors when garbage-collected from another thread."""
    entry = realtime._servers.get(asyncio.get_running_loop())
    if entry is not None:
        server, _task = entry
        with suppress(Exception):
            await server.stop()
        server.rooms.clear()
    gc.collect()


@pytest.fixture()
def ws_client(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    with anyio.from_thread.start_blocking_portal(backend="asyncio") as portal:
        client.portal = portal  # every websocket session now shares this loop
        yield client
        portal.call(_teardown_realtime)
        client.portal = None
    app.dependency_overrides.clear()


@pytest.fixture()
def concept(db, collection) -> Concept:
    """A concept in the conftest collection (edit_policy 'anyone')."""
    concept = Concept(collection_id=collection.id)
    db.add(concept)
    db.commit()
    return concept


def _connect(client: TestClient, concept_id: str, branch: str = "main", **params: str):
    url = f"/ws/collab/concept.{concept_id}.{branch}"
    query = "&".join(f"{key}={value}" for key, value in params.items())
    if query:
        url = f"{url}?{query}"
    return client.websocket_connect(url)


def _expect_step1(ws) -> None:
    """The server greets every admitted client with y-protocol SYNC_STEP1."""
    frame = ws.receive_bytes()
    assert frame[0] == YMESSAGE_SYNC
    assert frame[1] == YSYNC_STEP1


def _expect_close(ws, code: int) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        ws.receive_bytes()
    assert exc_info.value.code == code


def test_two_clients_in_one_room_sync_updates(ws_client, db, concept):
    """A Y update applied by one client reaches the other; one client uses the
    JWT query param, the other the DEV_AUTH who-fallback."""
    user = User(handle="tokenbararen", display_name="Tokenbäraren")
    db.add(user)
    db.commit()
    with (
        _connect(ws_client, concept.id, token=create_token(user.id)) as ws1,
        _connect(ws_client, concept.id, who="kollegan") as ws2,
    ):
        _expect_step1(ws1)
        _expect_step1(ws2)

        doc = Doc()
        doc["content"] = text = Text()
        text += "hej samarbete"
        ws1.send_bytes(create_update_message(doc.get_update()))

        frame = ws2.receive_bytes()
        assert frame[0] == YMESSAGE_SYNC
        assert frame[1] == YSYNC_UPDATE
        mirror = Doc()
        mirror["content"] = mirror_text = Text()
        mirror.apply_update(read_message(frame[2:]))
        assert str(mirror_text) == "hej samarbete"


def test_stranger_rejected_on_org_policy_collection(ws_client, db):
    org = Organisation(slug="agarorg", name="Ägarorg", is_approved=True)
    db.add(org)
    db.flush()
    coll = Collection(slug="orgsamling", name="Orgsamling", organisation_id=org.id)
    coll.edit_policy = "org"
    db.add(coll)
    db.flush()
    concept = Concept(collection_id=coll.id)
    db.add(concept)
    db.commit()

    with _connect(ws_client, concept.id, who="framling") as ws:
        _expect_close(ws, 4403)
    with _connect(ws_client, concept.id) as ws:  # anonymous
        _expect_close(ws, 4403)


def test_legacy_open_collection_rejects_anonymous_admits_identity(ws_client, db):
    """Migration 008: anonymous users are gone. A legacy 'open' row behaves
    as 'anyone' — an identity is required, anonymous is closed out."""
    coll = Collection(slug="wikilaget", name="Wikiläget", edit_policy="open")
    db.add(coll)
    db.flush()
    concept = Concept(collection_id=coll.id)
    db.add(concept)
    db.commit()

    with _connect(ws_client, concept.id) as ws:  # no token, no who
        _expect_close(ws, 4403)
    with _connect(ws_client, concept.id, who="inloggad") as ws:
        _expect_step1(ws)


def test_archived_collection_rejected(ws_client, db):
    """Archive trumps everything — even for an identity."""
    coll = Collection(slug="arkivet", name="Arkivet", edit_policy="open", is_archived=True)
    db.add(coll)
    db.flush()
    concept = Concept(collection_id=coll.id)
    db.add(concept)
    db.commit()

    with _connect(ws_client, concept.id, who="testare") as ws:
        _expect_close(ws, 4403)


def test_unknown_concept_and_malformed_room_rejected(ws_client, collection):
    with _connect(ws_client, "00000000-0000-0000-0000-000000000000", who="testare") as ws:
        _expect_close(ws, 4404)
    with ws_client.websocket_connect("/ws/collab/inte-ett-rumsnamn?who=testare") as ws:
        _expect_close(ws, 4404)


def test_locked_main_room_member_matrix(ws_client, db):
    """Locked collection: 'main' admits lock-exempt users only; non-main
    branch rooms admit any authenticated identity (mirrors mode=branch
    writes / the proposal flow); anonymous is always rejected."""
    org = Organisation(slug="lasorg", name="Låsorg", is_approved=True)
    db.add(org)
    db.flush()
    admin = User(handle="orgadmin", display_name="Orgadmin")
    editor = User(handle="orgeditor", display_name="Orgeditor")
    stranger = User(handle="utomstaende", display_name="Utomstående")
    coll = Collection(slug="last-samling", name="Låst samling", organisation_id=org.id)
    coll.edit_policy = "org"
    coll.is_locked = True
    db.add_all([admin, editor, stranger, coll])
    db.flush()
    # Multi-org (2026-07): roles live in org_memberships, not on the user.
    db.add_all(
        [
            OrgMembership(user_id=admin.id, organisation_id=org.id, role="admin"),
            OrgMembership(user_id=editor.id, organisation_id=org.id, role="editor"),
        ]
    )
    concept = Concept(collection_id=coll.id)
    db.add(concept)
    db.commit()

    # main: org admin is lock-exempt, org editor and strangers are not.
    with _connect(ws_client, concept.id, who="orgadmin") as ws:
        _expect_step1(ws)
    with _connect(ws_client, concept.id, who="orgeditor") as ws:
        _expect_close(ws, 4403)
    with _connect(ws_client, concept.id, who="utomstaende") as ws:
        _expect_close(ws, 4403)

    # non-main branch room: any authenticated identity, but never anonymous.
    with _connect(ws_client, concept.id, branch="forslag-1", who="orgeditor") as ws:
        _expect_step1(ws)
    with _connect(ws_client, concept.id, branch="forslag-1", who="utomstaende") as ws:
        _expect_step1(ws)
    with _connect(ws_client, concept.id, branch="forslag-1") as ws:
        _expect_close(ws, 4403)
