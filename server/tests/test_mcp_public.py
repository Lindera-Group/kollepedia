"""The public MCP endpoint at /mcp: read-only, anonymous visibility.

The session manager behind the Streamable HTTP transport can be started once
per process, so one TestClient with the MCP lifespan is shared by the module;
the tools' session factory is pointed at the per-test in-memory engine.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.applications import Starlette
from starlette.routing import Route

from app import mcp_public
from app.models import Collection
from tests.test_api import _create_concept

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.fixture(scope="module")
def mcp_client():
    @asynccontextmanager
    async def lifespan(_app):
        async with mcp_public.mcp.session_manager.run():
            yield

    test_app = Starlette(
        routes=[Route("/mcp", endpoint=mcp_public.asgi, methods=["GET", "POST", "DELETE"])],
        lifespan=lifespan,
    )
    with TestClient(test_app) as c:
        yield c


@pytest.fixture()
def mcp_db(engine, monkeypatch):
    monkeypatch.setattr(
        mcp_public,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
    )


def _rpc(mcp_client, method: str, params: dict | None = None, rid: int = 1):
    body: dict = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    resp = mcp_client.post("/mcp", headers=MCP_HEADERS, content=json.dumps(body))
    assert resp.status_code == 200, (resp.status_code, resp.text[:300])
    return resp.json()


def _call(mcp_client, name: str, arguments: dict):
    data = _rpc(mcp_client, "tools/call", {"name": name, "arguments": arguments}, rid=2)
    result = data["result"]
    if result.get("isError"):
        return None, result["content"][0]["text"]
    structured = result.get("structuredContent")
    if structured is not None:
        return structured.get("result", structured), None
    return json.loads(result["content"][0]["text"]), None


def test_tools_are_the_five_public_readers(mcp_client):
    data = _rpc(mcp_client, "tools/list")
    names = sorted(t["name"] for t in data["result"]["tools"])
    assert names == sorted(mcp_public.PUBLIC_TOOLS)
    assert not any(n.startswith(("create", "add", "update", "delete")) for n in names)


def test_search_and_read_see_only_public_collections(mcp_client, mcp_db, client, db, collection):
    # The hidden collection is public while the concept is written through the
    # API (the dev identity may not write into org-private space), then hidden.
    private = Collection(slug="intern-lista", name="Intern lista")
    db.add(private)
    db.commit()
    public_concept = _create_concept(client, collection.id, form="hållplats", definition="öppen")
    hidden = _create_concept(client, private.id, form="hemligt begrepp", definition="intern")
    private.visibility = "org_private"
    db.commit()

    hits, err = _call(mcp_client, "search_concepts", {"q": "hållplats"})
    assert err is None and [h["id"] for h in hits] == [public_concept["id"]]
    assert hits[0]["url"].endswith(f"/concepts/{public_concept['id']}")

    none, err = _call(mcp_client, "search_concepts", {"q": "hemligt"})
    assert err is None and none == []

    _, err = _call(mcp_client, "get_concept", {"concept_id": hidden["id"]})
    assert err is not None and "finns inte" in err

    detail, err = _call(mcp_client, "get_concept", {"concept_id": public_concept["id"]})
    assert err is None
    assert detail["canonical_form"] == "hållplats" and detail["version_count"] == 1

    history, err = _call(mcp_client, "get_concept_history", {"concept_id": public_concept["id"]})
    assert err is None and len(history["versions"]) == 1

    listed, err = _call(mcp_client, "list_collections", {})
    assert err is None
    slugs = {c["slug"] for c in listed}
    assert collection.slug in slugs and "intern-lista" not in slugs


def test_collection_detail_reports_export_rule(mcp_client, mcp_db, db):
    blocked = Collection(
        slug="tillstand",
        name="Tillstånd",
        licence={"label": "© X – no redistribution", "redistribution": "not_permitted"},
    )
    db.add(blocked)
    db.commit()
    detail, err = _call(mcp_client, "get_collection", {"slug": "tillstand"})
    assert err is None
    assert detail["export_allowed"] is False and "export_url" not in detail
    assert detail["licence"] == "© X – no redistribution"
