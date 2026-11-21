"""Regressionstester för säkerhetsfixarna 2026-07-15 (inför acceptanstestet).

Täcker de behörighetsgap som kodgenomgången pekade ut:
  • fästlistor var oskyddade (vem som helst kunde läsa/mutera vilken lista som helst)
  • /ai/draft skickade org-privat definitionstext till LLM utan view-koll
  • /ai/extract och /users saknade auth

Återanvänder org-scenariot från test_night4 (root/anna/cesar/bertil + org-ägd
samling som kan göras org_private).
"""

from app.models import ConceptRelation
from tests.test_night4 import (
    ANON,
    _bearer,
    _create_collection,
    _create_concept,
    _org_setup,
    _register,
)


def _make_org_private(client, coll, anna):
    client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"visibility": "org_private"},
        headers=_bearer(anna),
    )


# ── Fästlistor: privata per ägare ────────────────────────────────────────────


def test_lists_are_private_to_their_owner(client):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    mine = client.post("/api/v1/lists", json={"name": "Min profil"}, headers=_bearer(anna)).json()

    # Ägaren ser och läser sin lista.
    assert [ll["id"] for ll in client.get("/api/v1/lists", headers=_bearer(anna)).json()] == [
        mine["id"]
    ]
    assert client.get(f"/api/v1/lists/{mine['id']}", headers=_bearer(anna)).status_code == 200

    # En annan användare ser den inte i sin lista och får 404 på direktåtkomst
    # (existensen röjs inte).
    assert client.get("/api/v1/lists", headers=_bearer(bertil)).json() == []
    assert client.get(f"/api/v1/lists/{mine['id']}", headers=_bearer(bertil)).status_code == 404

    # Anonym ser inga listor och kan inte skapa.
    assert client.get("/api/v1/lists", headers=ANON).json() == []
    assert client.post("/api/v1/lists", json={"name": "x"}, headers=ANON).status_code == 401


def test_list_mutations_require_ownership(client):
    root, anna, cesar, bertil, coll, concept = _org_setup(client)
    mine = client.post("/api/v1/lists", json={"name": "Profil"}, headers=_bearer(anna)).json()

    # Främling kan inte lägga till eller ta bort objekt (404 — inte röjt).
    add_as_bertil = client.post(
        f"/api/v1/lists/{mine['id']}/items",
        json={"concept_id": concept["id"], "follow_head": True},
        headers=_bearer(bertil),
    )
    assert add_as_bertil.status_code == 404

    # Anonym likaså nekas (401).
    assert (
        client.post(
            f"/api/v1/lists/{mine['id']}/items",
            json={"concept_id": concept["id"], "follow_head": True},
            headers=ANON,
        ).status_code
        == 401
    )

    # Ägaren lägger till och tar bort som väntat.
    added = client.post(
        f"/api/v1/lists/{mine['id']}/items",
        json={"concept_id": concept["id"], "follow_head": True},
        headers=_bearer(anna),
    )
    assert added.status_code == 201
    item_id = added.json()["items"][0]["id"]
    assert (
        client.delete(
            f"/api/v1/lists/{mine['id']}/items/{item_id}", headers=_bearer(bertil)
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/lists/{mine['id']}/items/{item_id}", headers=_bearer(anna)
        ).status_code
        == 204
    )


def test_cannot_pin_a_concept_you_cannot_see(client):
    root, anna, cesar, bertil, coll, concept = _org_setup(client)
    _make_org_private(client, coll, anna)
    # bertil (icke-medlem) skapar en egen lista och försöker fästa ett begrepp
    # i den org-privata samlingen han inte får se → 404, inte läckt.
    bertil_list = client.post(
        "/api/v1/lists", json={"name": "Bertils"}, headers=_bearer(bertil)
    ).json()
    resp = client.post(
        f"/api/v1/lists/{bertil_list['id']}/items",
        json={"concept_id": concept["id"], "follow_head": True},
        headers=_bearer(bertil),
    )
    assert resp.status_code == 404


def test_list_export_is_owner_only(client):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    mine = client.post("/api/v1/lists", json={"name": "Profil"}, headers=_bearer(anna)).json()
    url = f"/api/v1/lists/{mine['id']}/export"
    assert client.get(url, headers=_bearer(anna)).status_code == 200
    assert client.get(url, headers=_bearer(bertil)).status_code == 404
    assert client.get(url, headers=ANON).status_code == 401


# ── AI: ingen org-privat läcka, auth krävs ───────────────────────────────────


def test_ai_draft_refuses_versions_you_cannot_see(client):
    root, anna, cesar, bertil, coll, concept = _org_setup(client)
    version_id = concept["head"]["id"]
    _make_org_private(client, coll, anna)
    # Icke-medlem med BYOK-nyckel får INTE ut org-privat text (404 som läsvägen).
    resp = client.post(
        "/api/v1/ai/draft",
        json={"version_ids": [version_id], "intent": "synthesize"},
        headers={**_bearer(bertil), "X-LLM-Key": "sk-test-dummy"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "version_not_found"
    # Anonym nekas redan på auth.
    assert (
        client.post(
            "/api/v1/ai/draft",
            json={"version_ids": [version_id], "intent": "synthesize"},
            headers={**ANON, "X-LLM-Key": "sk-test-dummy"},
        ).status_code
        == 401
    )


def test_ai_extract_requires_login(client):
    assert (
        client.post(
            "/api/v1/ai/extract",
            json={"text": "hållplats: en plats där fordon stannar"},
            headers={**ANON, "X-LLM-Key": "sk-test-dummy"},
        ).status_code
        == 401
    )


# ── Begreppssidan: länkar in i samlingar läsaren inte får se ─────────────────


def test_concept_names_only_relations_and_translations_the_reader_may_see(client, db):
    """A public concept related to, or translated by, a concept in an
    org-private collection: the relation and the translation are the members'
    to see. Everyone else gets neither the term nor the id."""
    root, anna, cesar, bertil, coll, internal = _org_setup(client)
    public = _create_collection(
        client, anna, slug="oppen-lista", organisation_id=coll["organisation"]["id"]
    )
    shown = _create_concept(client, public["id"], form="resa", headers=_bearer(anna)).json()
    translation = _create_concept(
        client,
        coll["id"],
        form="internal journey",
        language="en",
        translated_from_version_id=shown["head"]["id"],
        headers=_bearer(anna),
    ).json()
    db.add(
        ConceptRelation(
            relation_type="related_to", from_concept_id=shown["id"], to_concept_id=internal["id"]
        )
    )
    db.commit()
    _make_org_private(client, coll, anna)

    def linked(headers) -> tuple[list[str], list[str]]:
        resp = client.get(f"/api/v1/concepts/{shown['id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        return (
            [r["other_concept_id"] for r in body["relations"]],
            [t["concept_id"] for t in body["translations"]],
        )

    assert linked(_bearer(cesar)) == ([internal["id"]], [translation["id"]])
    assert linked(_bearer(bertil)) == ([], [])
    assert linked(ANON) == ([], [])
