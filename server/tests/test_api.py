"""API tests: concepts, versions, the /graph payload, and pinned lists."""


def _create_concept(client, collection_id, form="hållplats", definition="En plats.", **kwargs):
    payload = {
        "collection_id": collection_id,
        "canonical_form": form,
        "definition_md": definition,
        **kwargs,
    }
    resp = client.post("/api/v1/concepts", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _head(client, concept_id):
    resp = client.get(f"/api/v1/concepts/{concept_id}")
    assert resp.status_code == 200
    return resp.json()["head"]


def test_create_and_get_concept_shape(client, collection):
    created = _create_concept(client, collection.id, definition="En plats där bussar stannar.")

    resp = client.get(f"/api/v1/concepts/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"]["slug"] == "testsamling"
    assert body["version_count"] == 1
    assert body["head"]["canonical_form"] == "hållplats"
    assert body["head"]["definition_md"] == "En plats där bussar stannar."
    assert [b["name"] for b in body["branches"]] == ["main"]
    assert body["branches"][0]["head_version_id"] == body["head"]["id"]


def test_revise_via_api_moves_head_and_preserves_old(client, collection):
    concept = _create_concept(client, collection.id, definition="gammal text")
    v1 = concept["head"]

    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": v1["id"],
            "canonical_form": "hållplats",
            "definition_md": "ny text",
        },
    )
    assert resp.status_code == 201
    v2 = resp.json()

    head = _head(client, concept["id"])
    assert head["id"] == v2["id"]
    assert head["definition_md"] == "ny text"

    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    old = next(v for v in graph["versions"] if v["id"] == v1["id"])
    assert old["definition_md"] == "gammal text"


def test_revise_with_stale_base_returns_409(client, collection):
    concept = _create_concept(client, collection.id)
    v1 = concept["head"]
    payload = {
        "mode": "revise",
        "base_version_id": v1["id"],
        "canonical_form": "hållplats",
        "definition_md": "v2",
    }
    first = client.post(f"/api/v1/concepts/{concept['id']}/versions", json=payload)
    assert first.status_code == 201
    resp = client.post(f"/api/v1/concepts/{concept['id']}/versions", json=payload)
    assert resp.status_code == 409


def test_branch_without_name_returns_422(client, collection):
    concept = _create_concept(client, collection.id)
    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "branch",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "hållplats",
            "definition_md": "gren",
        },
    )
    assert resp.status_code == 422


def test_branch_creates_branch_and_duplicate_name_conflicts(client, collection):
    concept = _create_concept(client, collection.id)
    payload = {
        "mode": "branch",
        "base_version_id": concept["head"]["id"],
        "branch_name": "alternativ-tolkning",
        "canonical_form": "hållplats",
        "definition_md": "avvikande tolkning",
    }
    resp = client.post(f"/api/v1/concepts/{concept['id']}/versions", json=payload)
    assert resp.status_code == 201
    branch_version = resp.json()

    body = client.get(f"/api/v1/concepts/{concept['id']}").json()
    branches = {b["name"]: b for b in body["branches"]}
    assert set(branches) == {"main", "alternativ-tolkning"}
    assert branches["alternativ-tolkning"]["head_version_id"] == branch_version["id"]
    assert branches["main"]["head_version_id"] == concept["head"]["id"]

    duplicate = client.post(f"/api/v1/concepts/{concept['id']}/versions", json=payload)
    assert duplicate.status_code == 409


def test_synthesize_with_extra_parents_via_api(client, collection):
    concept = _create_concept(client, collection.id)
    v1 = concept["head"]
    branch_version = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "branch",
            "base_version_id": v1["id"],
            "branch_name": "gren",
            "canonical_form": "hållplats",
            "definition_md": "grentext",
        },
    ).json()
    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "synthesize",
            "base_version_id": v1["id"],
            "extra_parent_ids": [branch_version["id"]],
            "canonical_form": "hållplats",
            "definition_md": "syntes",
        },
    )
    assert resp.status_code == 201
    synthesis = resp.json()

    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    syn_edges = sorted(
        (e for e in graph["edges"] if e["child_id"] == synthesis["id"]),
        key=lambda e: e["ordinal"],
    )
    assert [(e["parent_id"], e["edge_type"], e["ordinal"]) for e in syn_edges] == [
        (v1["id"], "synthesized_from", 0),
        (branch_version["id"], "synthesized_from", 1),
    ]
    assert _head(client, concept["id"])["id"] == synthesis["id"]


def test_promote_via_api(client, collection):
    concept = _create_concept(client, collection.id, definition="originaltext")
    v1 = concept["head"]
    v2 = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": v1["id"],
            "canonical_form": "hållplats",
            "definition_md": "nyare text",
        },
    ).json()

    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/promote", json={"version_id": v1["id"]}
    )
    assert resp.status_code == 201
    promoted = resp.json()
    assert promoted["definition_md"] == "originaltext"
    assert _head(client, concept["id"])["id"] == promoted["id"]

    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    edges = {
        e["edge_type"]: e["parent_id"] for e in graph["edges"] if e["child_id"] == promoted["id"]
    }
    assert edges == {"promoted_from": v1["id"], "revised_from": v2["id"]}


def test_translated_from_at_creation_creates_edge_and_translation(client, collection):
    sv = _create_concept(client, collection.id, form="hållplats", definition="En plats.")
    en = _create_concept(
        client,
        collection.id,
        form="stop",
        definition="A place.",
        language="en",
        translated_from_version_id=sv["head"]["id"],
    )

    graph = client.get(f"/api/v1/concepts/{en['id']}/graph").json()
    edge = next(e for e in graph["edges"] if e["child_id"] == en["head"]["id"])
    assert edge["edge_type"] == "translated_from"
    assert edge["parent_id"] == sv["head"]["id"]

    sv_body = client.get(f"/api/v1/concepts/{sv['id']}").json()
    assert [t["concept_id"] for t in sv_body["translations"]] == [en["id"]]


def test_graph_endpoint_returns_versions_ascending_edges_and_branches(client, collection):
    concept = _create_concept(client, collection.id)
    base = concept["head"]["id"]
    for i in range(2):
        base = client.post(
            f"/api/v1/concepts/{concept['id']}/versions",
            json={
                "mode": "revise",
                "base_version_id": base,
                "canonical_form": "hållplats",
                "definition_md": f"revision {i}",
            },
        ).json()["id"]
    client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "branch",
            "base_version_id": concept["head"]["id"],
            "branch_name": "gren",
            "canonical_form": "hållplats",
            "definition_md": "grentext",
        },
    )

    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    assert len(graph["versions"]) == 4
    created = [v["created_at"] for v in graph["versions"]]
    assert created == sorted(created)
    assert len(graph["edges"]) == 3  # two revisions + one branch, all with parent edges
    assert {b["name"] for b in graph["branches"]} == {"main", "gren"}
    assert graph["collection"]["slug"] == "testsamling"


def test_pinned_list_export_survives_later_revision(client, collection):
    """VISION §9.2: a pinned list keeps quoting the pinned version even after
    the concept's head moves on; follow_head items track the newest text."""
    followed = _create_concept(client, collection.id, form="linje", definition="följer huvudet")
    pinned = _create_concept(client, collection.id, form="zon", definition="fastnålad lydelse")

    lst = client.post("/api/v1/lists", json={"name": "Upphandlingsprofil", "purpose": "Demo"})
    assert lst.status_code == 201
    list_id = lst.json()["id"]

    assert (
        client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"concept_id": followed["id"], "follow_head": True},
        ).status_code
        == 201
    )
    # Pin without explicit version_id: pins the *current* head explicitly.
    assert (
        client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"concept_id": pinned["id"], "follow_head": False},
        ).status_code
        == 201
    )

    # Both concepts move on.
    for concept, new_text in ((followed, "ny följd text"), (pinned, "ändrad lydelse")):
        resp = client.post(
            f"/api/v1/concepts/{concept['id']}/versions",
            json={
                "mode": "revise",
                "base_version_id": concept["head"]["id"],
                "canonical_form": concept["head"]["canonical_form"],
                "definition_md": new_text,
            },
        )
        assert resp.status_code == 201

    export = client.get(f"/api/v1/lists/{list_id}/export", params={"format": "markdown"})
    assert export.status_code == 200
    text = export.text
    assert "fastnålad lydelse" in text  # pinned version text, despite the later revision
    assert "ändrad lydelse" not in text
    assert "ny följd text" in text  # follow_head shows the new head
    assert "följer huvudet" not in text


def test_legacy_prototype_id_resolves_to_concept(client, db):
    """Imported [Label](#old-term-id) links: the alias table translates
    prototype term_ids transparently in every concept read (migrate_006)."""
    from app.models import LegacyId

    # Org-less collections are PRIVATE sandboxes now (funnel, 2026-07) — the
    # dev X-User 'testare' is no super admin, so public would be a 422.
    coll = client.post(
        "/api/v1/collections",
        json={"slug": "legacy-coll", "name": "Legacy", "visibility": "private"},
    ).json()
    concept = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": coll["id"],
            "canonical_form": "gammalt id-prov",
            "definition_md": "En definition.",
        },
    ).json()
    db.add(
        LegacyId(legacy_id="00000000-dead-beef-0000-000000000001", concept_id=concept["id"])
    )
    db.commit()

    aliased = client.get("/api/v1/concepts/00000000-dead-beef-0000-000000000001")
    assert aliased.status_code == 200
    assert aliased.json()["id"] == concept["id"]
    # The graph payload follows the same lookup.
    graph_res = client.get("/api/v1/concepts/00000000-dead-beef-0000-000000000001/graph")
    assert graph_res.status_code == 200
    # Unknown ids still 404.
    assert client.get("/api/v1/concepts/00000000-dead-beef-0000-00000000dead").status_code == 404
