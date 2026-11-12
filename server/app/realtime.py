"""Real-time collaborative drafting: a Yjs websocket sync relay.

Multiple users co-edit a draft through TipTap/Yjs on the frontend; this module
relays the y-protocol between them. Rooms are EPHEMERAL and in-memory only —
room `concept.<concept_id>.<branch_name>` holds the in-flight draft, nothing
is persisted here, and the append-only version graph is only ever written
through POST /concepts/{id}/versions. A lost room (deploy, crash) just means
peers re-seed the document from the concept head.

Integration pattern (pycrdt-websocket 0.16, installs as `pycrdt.websocket`):
one in-memory `WebsocketServer` per event loop, started lazily as a background
task on the first connection (uvicorn has exactly one loop, so production gets
exactly one server; test portals each get their own). `_Channel` is the thin
adapter implementing pycrdt's Channel protocol (path / send / recv /
async-iteration) over an accepted FastAPI WebSocket — `WebsocketServer.serve`
keys its room registry by `channel.path`, auto-creates missing rooms and
deletes a room when its last client leaves (auto_clean_rooms=True; verified in
pycrdt.websocket.websocket_server.WebsocketServer.serve). Awareness/presence
frames are relayed by the y-protocol itself — no server logic here.

Auth is checked BEFORE accepting, but rejections are delivered as
accept-then-close(4403/4404): a pre-accept close surfaces to browsers as an
opaque HTTP 403 during the handshake, while the JS WebSocket API only exposes
close codes from a real close frame — so we accept, close with the code, and
the frontend can tell "no such concept" from "not allowed".
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pycrdt.websocket import WebsocketServer, exception_logger
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from .db import get_db
from .deps import can_view_collection, ensure_write_allowed, resolve_ws_user
from .models import Concept, User

logger = logging.getLogger("kollepedia.realtime")

router = APIRouter(tags=["realtime"])

# Application close codes (4000–4999 is the RFC 6455 private range).
CLOSE_FORBIDDEN = 4403  # authenticated-or-not, you may not edit here
CLOSE_NOT_FOUND = 4404  # unknown/invisible concept or malformed room name

# One relay per event loop, torn down with its loop (the done-callback pops
# the entry when the start task is cancelled at loop shutdown).
_servers: dict[asyncio.AbstractEventLoop, tuple[WebsocketServer, "asyncio.Task[None]"]] = {}


async def _get_websocket_server() -> WebsocketServer:
    loop = asyncio.get_running_loop()
    entry = _servers.get(loop)
    if entry is None:
        server = WebsocketServer(
            auto_clean_rooms=True, exception_handler=exception_logger, log=logger
        )
        task = loop.create_task(server.start())
        task.add_done_callback(lambda _t, loop=loop: _servers.pop(loop, None))
        entry = (server, task)
        _servers[loop] = entry
    server = entry[0]
    await server.started.wait()
    return server


class _Channel:
    """pycrdt `Channel` over an accepted FastAPI/Starlette WebSocket.

    `path` is the ROOM NAME (not the URL path) — it is what
    `WebsocketServer.serve` keys the room registry by.
    """

    def __init__(self, websocket: WebSocket, path: str) -> None:
        self._websocket = websocket
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def __aiter__(self) -> "_Channel":
        return self

    async def __anext__(self) -> bytes:
        # KeyError: a (protocol-violating) text frame; treat it as a hangup
        # rather than letting it kill the room for the other collaborators.
        try:
            return await self._websocket.receive_bytes()
        except (WebSocketDisconnect, KeyError, RuntimeError):
            raise StopAsyncIteration from None

    async def recv(self) -> bytes:
        return await self._websocket.receive_bytes()

    async def send(self, message: bytes) -> None:
        try:
            await self._websocket.send_bytes(message)
        except (WebSocketDisconnect, RuntimeError):
            # Peer already gone mid-broadcast; the recv side unregisters it.
            pass


def _parse_room(room: str) -> tuple[str, str] | None:
    """`concept.<concept_id>.<branch_name>` → (concept_id, branch_name).

    Concept ids are UUIDs (never contain dots); branch names may, so only the
    first two dots split."""
    parts = room.split(".", 2)
    if len(parts) != 3 or parts[0] != "concept" or not parts[1] or not parts[2]:
        return None
    return parts[1], parts[2]


def _close_reason(detail: str) -> str:
    """RFC 6455 caps close reasons at 123 UTF-8 bytes; truncate safely."""
    return detail.encode()[:120].decode(errors="ignore")


def _authorize(db: Session, room: str, user: User | None) -> tuple[int, str] | None:
    """Room admission = the concept-write permission, verbatim.

    Returns (close_code, reason) to reject, or None to admit. Joining the
    'main' room requires exactly what a main-line version write requires
    (archived → reject; locked → lock-exempt users only); joining any other
    branch room mirrors mode=branch writes (branch_exempt: any authenticated
    identity may draft on a non-main branch of locked content — the proposal
    flow). Anonymous connections are always rejected (migration 008)."""
    parsed = _parse_room(room)
    if parsed is None:
        return CLOSE_NOT_FOUND, "Okänt rum."
    concept_id, branch_name = parsed
    concept = db.get(Concept, concept_id)
    # org_private concepts are 4404 for outsiders — existence is not disclosed.
    if concept is None or not can_view_collection(user, concept.collection):
        return CLOSE_NOT_FOUND, "Okänt begrepp."
    try:
        ensure_write_allowed(user, concept.collection, branch_exempt=branch_name != "main")
    except HTTPException as exc:
        return CLOSE_FORBIDDEN, _close_reason(str(exc.detail))
    return None


@router.websocket("/ws/collab/{room}")
async def collab_room(
    websocket: WebSocket,
    room: str,
    token: str | None = Query(default=None),
    who: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    user = resolve_ws_user(token, who, db)
    rejection = _authorize(db, room, user)
    # Return the pooled connection before the (long-lived) sync phase — a
    # handful of collaborators must not exhaust the engine pool. The get_db
    # teardown close at disconnect is a harmless no-op.
    db.close()
    await websocket.accept()
    if rejection is not None:
        code, reason = rejection
        await websocket.close(code=code, reason=reason)
        return
    server = await _get_websocket_server()
    try:
        await server.serve(_Channel(websocket, room))
    finally:
        # If the room died server-side the client may still be connected;
        # closing an already-closed socket raises — ignore it.
        try:
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass
