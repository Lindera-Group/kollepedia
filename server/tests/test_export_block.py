"""Collections published by permission without redistribution rights: readable,
searchable, never exported as a file (beslut 2026-11-08)."""

from __future__ import annotations

from app.models import Collection
from tests.test_api import _create_concept

NO_REDISTRIBUTION = {
    "label": "© Exempel AB – published by permission, no redistribution",
    "basis": "published_with_permission",
    "redistribution": "not_permitted",
}


def _blocked_collection(db) -> Collection:
    coll = Collection(slug="tillstandslistan", name="Tillståndslistan", licence=NO_REDISTRIBUTION)
    db.add(coll)
    db.commit()
    return coll


def test_collection_export_is_refused_when_licence_forbids_redistribution(client, db):
    coll = _blocked_collection(db)
    _create_concept(client, coll.id, form="resa", definition="förflyttning med tillstånd")

    for fmt in ("csv", "markdown", "jsonld", "skos", "tbx"):
        resp = client.get(f"/api/v1/collections/{coll.slug}/export?format={fmt}")
        assert resp.status_code == 403, fmt
        body = resp.json()
        assert body["detail"]["code"] == "export_not_permitted"
        assert "Exempel AB" in body["detail"]["params"]["licence"]

    # Reading stays open: the page and the API still serve the content.
    detail = client.get(f"/api/v1/collections/{coll.slug}")
    assert detail.status_code == 200
    assert detail.json()["export_allowed"] is False


def test_ordinary_collections_keep_exporting(client, collection):
    _create_concept(client, collection.id, form="linje", definition="fri att sprida")
    assert (
        client.get(f"/api/v1/collections/{collection.slug}/export?format=csv").status_code == 200
    )
    assert client.get(f"/api/v1/collections/{collection.slug}").json()["export_allowed"] is True


def test_list_export_omits_concepts_from_blocked_collections(client, db, collection):
    blocked = _blocked_collection(db)
    free = _create_concept(client, collection.id, form="hållplats", definition="fri")
    locked = _create_concept(client, blocked.id, form="zon", definition="med tillstånd")

    lst = client.post("/api/v1/lists", json={"name": "Blandad lista", "purpose": "Test"})
    assert lst.status_code == 201
    list_id = lst.json()["id"]
    for concept in (free, locked):
        assert (
            client.post(
                f"/api/v1/lists/{list_id}/items",
                json={"concept_id": concept["id"], "follow_head": True},
            ).status_code
            == 201
        )

    resp = client.get(f"/api/v1/lists/{list_id}/export?format=markdown")
    assert resp.status_code == 200
    text = resp.text
    assert "hållplats" in text
    assert "med tillstånd" not in text
    assert "1 begrepp utelämnade" in text


def test_list_item_cannot_pin_a_version_from_another_concept(client, collection):
    a = _create_concept(client, collection.id, form="a", definition="första")
    b = _create_concept(client, collection.id, form="b", definition="andra")
    b_head = client.get(f"/api/v1/concepts/{b['id']}").json()["head"]["id"]
    lst = client.post("/api/v1/lists", json={"name": "Lista", "purpose": "Test"})
    resp = client.post(
        f"/api/v1/lists/{lst.json()['id']}/items",
        json={"concept_id": a["id"], "version_id": b_head, "follow_head": False},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "version_mismatch"
