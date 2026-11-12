"""Roadmap night-sweep tests: users search, DELETEs, exports, AI drafts."""

import json
import xml.etree.ElementTree as ET

from app.models import User

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _create_concept(client, collection_id, form="hållplats", definition="En plats.", **kwargs):
    headers = kwargs.pop("headers", None)
    payload = {
        "collection_id": collection_id,
        "canonical_form": form,
        "definition_md": definition,
        **kwargs,
    }
    resp = client.post("/api/v1/concepts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------
# Users search
# --------------------------------------------------------------------------


def test_users_search_orders_by_display_name(client, db):
    db.add_all(
        [
            User(handle="zorn", display_name="Anders Zorn"),
            User(handle="ada", display_name="Ada Lovelace"),
            User(handle="linnea", display_name="Linnéa Berg"),
        ]
    )
    db.commit()
    # Login-gated (säkerhetsfix 2026-07-15): anonymous is refused.
    anon = client.get("/api/v1/users", headers={"X-User": ""})
    assert anon.status_code == 401
    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    names = [u["display_name"] for u in resp.json()]
    # The three seeded users appear in display-name order (the authenticated
    # caller may also be listed — assert the relative order, not equality).
    seeded = [n for n in names if n in {"Ada Lovelace", "Anders Zorn", "Linnéa Berg"}]
    assert seeded == ["Ada Lovelace", "Anders Zorn", "Linnéa Berg"]


def test_users_search_filters_on_handle_and_display_name(client, db):
    db.add_all(
        [
            User(handle="martin", display_name="Martin Nordström"),
            User(handle="ada", display_name="Ada Lovelace"),
        ]
    )
    db.commit()
    by_handle = client.get("/api/v1/users", params={"q": "mart"}).json()
    assert [u["handle"] for u in by_handle] == ["martin"]
    by_name = client.get("/api/v1/users", params={"q": "lovel"}).json()
    assert [u["handle"] for u in by_name] == ["ada"]
    assert client.get("/api/v1/users", params={"q": "nomatch"}).json() == []


# --------------------------------------------------------------------------
# DELETE endpoints
# --------------------------------------------------------------------------


def test_delete_relation(client, collection):
    a = _create_concept(client, collection.id, form="buss")
    b = _create_concept(client, collection.id, form="fordon")
    created = client.post(
        "/api/v1/relations",
        json={"relation_type": "broader", "from_concept_id": a["id"], "to_concept_id": b["id"]},
    )
    assert created.status_code == 201
    relation_id = created.json()["id"]

    resp = client.delete(f"/api/v1/relations/{relation_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/concepts/{a['id']}").json()["relations"] == []
    assert client.delete(f"/api/v1/relations/{relation_id}").status_code == 404


def test_delete_list_item_reorders_ordinals(client, collection):
    concepts = [
        _create_concept(client, collection.id, form=form) for form in ("alfa", "beta", "gamma")
    ]
    list_id = client.post("/api/v1/lists", json={"name": "Testlista"}).json()["id"]
    for concept in concepts:
        assert (
            client.post(
                f"/api/v1/lists/{list_id}/items",
                json={"concept_id": concept["id"], "follow_head": True},
            ).status_code
            == 201
        )
    items = client.get(f"/api/v1/lists/{list_id}").json()["items"]
    middle = items[1]

    assert client.delete(f"/api/v1/lists/{list_id}/items/{middle['id']}").status_code == 204
    remaining = client.get(f"/api/v1/lists/{list_id}").json()["items"]
    assert [i["canonical_form"] for i in remaining] == ["alfa", "gamma"]
    assert [i["ordinal"] for i in remaining] == [0, 1]
    # Wrong list / already deleted → 404.
    assert client.delete(f"/api/v1/lists/{list_id}/items/{middle['id']}").status_code == 404
    assert client.delete(f"/api/v1/lists/other/items/{remaining[0]['id']}").status_code == 404


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------


def test_collection_export_csv(client, collection):
    _create_concept(
        client,
        collection.id,
        definition="En plats där fordon stannar.",
        tags=["Infrastruktur", "Drift"],
        headers={"X-User": "Martin"},
    )
    resp = client.get("/api/v1/collections/testsamling/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="testsamling.csv"' in resp.headers["content-disposition"]
    lines = resp.text.splitlines()
    assert lines[0].startswith("canonical_form,language,definition,status,tags,collection")
    assert "hållplats" in resp.text
    assert "Infrastruktur;Drift" in resp.text
    assert "Martin" in resp.text


def test_collection_export_markdown(client, collection):
    _create_concept(client, collection.id, definition="En plats där fordon stannar.")
    resp = client.get("/api/v1/collections/testsamling/export", params={"format": "markdown"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text.startswith("# Testsamling")
    assert "## hållplats" in resp.text
    assert "En plats där fordon stannar." in resp.text


def test_collection_export_jsonld(client, collection):
    concept = _create_concept(client, collection.id, headers={"X-User": "Martin"})
    resp = client.get("/api/v1/collections/testsamling/export", params={"format": "jsonld"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/ld+json")
    doc = json.loads(resp.text)
    assert doc["@context"]["skos"] == "http://www.w3.org/2004/02/skos/core#"
    node = next(n for n in doc["@graph"] if n["@id"] == f"urn:kollepedia:concept:{concept['id']}")
    assert node["skos:prefLabel"] == {"@value": "hållplats", "@language": "sv"}
    assert node["skos:definition"]["@language"] == "sv"
    assert node["prov:wasAttributedTo"] == "Martin"
    assert "dct:created" in node


def test_collection_export_skos_turtle_with_relations(client, collection):
    a = _create_concept(
        client, collection.id, form="buss", definition='Ett "stort" fordon.\nMed radbrytning.'
    )
    b = _create_concept(client, collection.id, form="fordon")
    client.post(
        "/api/v1/relations",
        json={"relation_type": "broader", "from_concept_id": a["id"], "to_concept_id": b["id"]},
    )
    resp = client.get("/api/v1/collections/testsamling/export", params={"format": "skos"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/turtle")
    text = resp.text
    assert text.startswith("@prefix skos: <http://www.w3.org/2004/02/skos/core#> .")
    assert "@prefix prov:" in text and "@prefix dct:" in text
    assert 'skos:prefLabel "buss"@sv' in text
    assert f"skos:broader <urn:kollepedia:concept:{b['id']}>" in text
    # Turtle escaping: no raw newline inside a literal, quotes escaped.
    assert '\\"stort\\"' in text and "\\nMed radbrytning." in text
    # Rudimentary well-formedness: every statement line ends with ; , or .
    for line in text.splitlines():
        if line.strip() and not line.startswith("@prefix"):
            assert line.rstrip().endswith((";", ".", ",")), line


def test_collection_export_tbx_with_translation_langset(client, collection):
    sv = _create_concept(client, collection.id, form="hållplats", definition="En plats.")
    _create_concept(
        client,
        collection.id,
        form="stop",
        definition="A place.",
        language="en",
        translated_from_version_id=sv["head"]["id"],
    )
    resp = client.get("/api/v1/collections/testsamling/export", params={"format": "tbx"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(resp.text)  # well-formed XML
    assert root.tag == "martif" and root.get("type") == "TBX"
    entries = {e.get("id"): e for e in root.iter("termEntry")}
    sv_entry = entries[f"c-{sv['id']}"]
    lang_sets = {ls.get(XML_LANG): ls.findtext("tig/term") for ls in sv_entry.iter("langSet")}
    assert lang_sets == {"sv": "hållplats", "en": "stop"}
    assert sv_entry.findtext('descrip[@type="definition"]') == "En plats."


def test_collection_export_unknown_format_and_slug(client, collection):
    _create_concept(client, collection.id)
    assert (
        client.get("/api/v1/collections/testsamling/export", params={"format": "docx"}).status_code
        == 422
    )
    assert (
        client.get("/api/v1/collections/finns-inte/export", params={"format": "csv"}).status_code
        == 404
    )


def test_list_export_csv_uses_pinned_version(client, collection):
    concept = _create_concept(client, collection.id, form="zon", definition="fastnålad lydelse")
    list_id = client.post("/api/v1/lists", json={"name": "Upphandlingsprofil"}).json()["id"]
    client.post(
        f"/api/v1/lists/{list_id}/items",
        json={"concept_id": concept["id"], "follow_head": False},
    )
    client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "zon",
            "definition_md": "ändrad lydelse",
        },
    )
    resp = client.get(f"/api/v1/lists/{list_id}/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="upphandlingsprofil.csv"' in resp.headers["content-disposition"]
    assert "fastnålad lydelse" in resp.text
    assert "ändrad lydelse" not in resp.text
    assert "testsamling" in resp.text  # each item carries its concept's collection slug


def test_list_export_jsonld_and_unknown_list(client, collection):
    concept = _create_concept(client, collection.id)
    list_id = client.post("/api/v1/lists", json={"name": "Liten lista"}).json()["id"]
    client.post(
        f"/api/v1/lists/{list_id}/items",
        json={"concept_id": concept["id"], "follow_head": True},
    )
    resp = client.get(f"/api/v1/lists/{list_id}/export", params={"format": "jsonld"})
    assert resp.status_code == 200
    doc = json.loads(resp.text)
    assert [n["@id"] for n in doc["@graph"]] == [f"urn:kollepedia:concept:{concept['id']}"]
    assert client.get("/api/v1/lists/nope/export").status_code == 404


# --------------------------------------------------------------------------
# AI drafts
# --------------------------------------------------------------------------


def test_ai_draft_requires_key(client, collection):
    concept = _create_concept(client, collection.id)
    resp = client.post(
        "/api/v1/ai/draft",
        json={"intent": "translate", "version_ids": [concept["head"]["id"]]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "ai_key_missing"


def test_ai_draft_rejects_empty_and_unknown_versions(client, collection):
    headers = {"X-LLM-Key": "sk-test", "X-LLM-Provider": "anthropic"}
    empty = client.post(
        "/api/v1/ai/draft", json={"intent": "synthesize", "version_ids": []}, headers=headers
    )
    assert empty.status_code == 400
    unknown = client.post(
        "/api/v1/ai/draft",
        json={"intent": "synthesize", "version_ids": ["not-a-version"]},
        headers=headers,
    )
    assert unknown.status_code == 400
    detail = unknown.json()["detail"]
    assert detail["code"] == "version_not_found"
    assert detail["params"]["version_id"] == "not-a-version"


def test_ai_draft_rejects_unknown_provider(client, collection):
    # 'openai' and 'berget' became valid providers in iteration 4 — a genuinely
    # unknown one is still a 400.
    concept = _create_concept(client, collection.id)
    resp = client.post(
        "/api/v1/ai/draft",
        json={"intent": "translate", "version_ids": [concept["head"]["id"]]},
        headers={"X-LLM-Key": "sk-test", "X-LLM-Provider": "mistral"},
    )
    assert resp.status_code == 400


def test_ai_draft_happy_path_with_mocked_provider(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    concept = _create_concept(client, collection.id, definition="En plats där fordon stannar.")
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "```json\n"
                            '{"canonical_form": "stop", '
                            '"definition_md": "A place where vehicles stop.", '
                            '"note_suggestion": "Translated from Swedish."}\n'
                            "```"
                        ),
                    }
                ]
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(ai_module.httpx, "post", fake_post)
    resp = client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "translate",
            "version_ids": [concept["head"]["id"]],
            "target_language": "en",
            "guidance": "Behåll Transmodel-terminologi.",
        },
        headers={"X-LLM-Key": "sk-test-123", "X-LLM-Provider": "anthropic"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "canonical_form": "stop",
        "definition_md": "A place where vehicles stop.",
        "note_suggestion": "Translated from Swedish.",
        "model": "claude-sonnet-5",
        "provider": "anthropic",
        "prompt_id": None,
    }
    # Provider call shape per the Messages API contract.
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-test-123"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["body"]["model"] == "claude-sonnet-5"
    assert captured["body"]["max_tokens"] == 1500
    assert captured["timeout"] == 60.0
    prompt = captured["body"]["messages"][0]["content"]
    assert "hållplats" in prompt and "Target language: en" in prompt
    assert "Behåll Transmodel-terminologi." in prompt


def test_ai_draft_provider_error_maps_to_502_without_key_echo(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    concept = _create_concept(client, collection.id)

    class FakeResponse:
        status_code = 401

        @staticmethod
        def json():
            return {"error": {"type": "authentication_error", "message": "invalid x-api-key"}}

    monkeypatch.setattr(ai_module.httpx, "post", lambda *a, **kw: FakeResponse())
    resp = client.post(
        "/api/v1/ai/draft",
        json={"intent": "synthesize", "version_ids": [concept["head"]["id"]]},
        headers={"X-LLM-Key": "sk-secret-key", "X-LLM-Provider": "anthropic"},
    )
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "ai_provider_error"
    assert detail["params"]["http_status"] == 401
    assert detail["params"]["error_type"] == "authentication_error"
    assert "sk-secret-key" not in resp.text
