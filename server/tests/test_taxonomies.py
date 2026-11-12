"""Taxonomies (plan NG_TAXONOMIES, 2026-07-11): curated vocabularies with two
scopes — global categories (super-admin-curated, deliberately mutable) and
collection taxonomies (e.g. Parts, min=max=1). Assignments live on the
CONCEPT; max_per_concept is hard, min is soft."""

from tests.test_night3 import (
    _bearer,
    _create_collection,
    _create_concept,
    _create_org,
    _register,
)

ANON = {"X-User": ""}


def _setup(client):
    """root (super admin), anna (approved-org admin) + a public collection."""
    root = _register(client, "root")
    anna = _register(client, "anna")
    org = _create_org(client, anna)
    client.post("/api/v1/orgs/k2/approve", headers=_bearer(root))
    coll = _create_collection(client, anna, slug="k2-ordlista", organisation_id=org["id"])
    concept = _create_concept(client, coll["id"], form="resa", headers=_bearer(anna)).json()
    return root, anna, coll, concept


def _global_taxonomy(client, root):
    resp = client.post(
        "/api/v1/taxonomies",
        json={"slug": "kategorier", "name": "Kategorier", "scope": "global",
              "min_per_concept": 1},
        headers=_bearer(root),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_value(client, taxonomy_id, name, headers):
    resp = client.post(
        f"/api/v1/taxonomies/{taxonomy_id}/values", json={"name": name}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_global_taxonomy_is_super_admin_curated(client):
    root, anna, _coll, _concept = _setup(client)
    # Only super admins create/curate GLOBAL taxonomies.
    denied = client.post(
        "/api/v1/taxonomies",
        json={"slug": "kategorier", "name": "Kategorier", "scope": "global"},
        headers=_bearer(anna),
    )
    assert denied.status_code == 403
    tax = _global_taxonomy(client, root)
    assert (
        client.post(
            f"/api/v1/taxonomies/{tax['id']}/values",
            json={"name": "Operations"},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    value = _add_value(client, tax["id"], "Operations", _bearer(root))
    # Duplicate value name → 409; rename via PATCH works.
    assert (
        client.post(
            f"/api/v1/taxonomies/{tax['id']}/values",
            json={"name": "Operations"},
            headers=_bearer(root),
        ).status_code
        == 409
    )
    renamed = client.patch(
        f"/api/v1/taxonomy-values/{value['id']}",
        json={"name": "Drift"},
        headers=_bearer(root),
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Drift"


def test_collection_taxonomy_is_curated_by_collection_managers(client):
    root, anna, coll, _concept = _setup(client)
    bertil = _register(client, "bertil")
    payload = {
        "slug": "parts", "name": "Delar", "scope": "collection",
        "collection_id": coll["id"], "min_per_concept": 1, "max_per_concept": 1,
    }
    assert (
        client.post("/api/v1/taxonomies", json=payload, headers=_bearer(bertil)).status_code
        == 403
    )
    created = client.post("/api/v1/taxonomies", json=payload, headers=_bearer(anna))
    assert created.status_code == 201, created.text
    # Listing with the collection returns global + the collection's own.
    _global_taxonomy(client, root)
    listed = client.get("/api/v1/taxonomies", params={"collection": coll["slug"]}).json()
    assert {t["slug"] for t in listed} == {"kategorier", "parts"}
    # Without collection param: global only.
    assert {t["slug"] for t in client.get("/api/v1/taxonomies").json()} == {"kategorier"}


def test_assignment_lives_on_concept_and_respects_max(client):
    root, anna, coll, concept = _setup(client)
    tax = _global_taxonomy(client, root)
    drift = _add_value(client, tax["id"], "Drift", _bearer(root))
    fordon = _add_value(client, tax["id"], "Transport Modes", _bearer(root))

    url = f"/api/v1/concepts/{concept['id']}/taxonomies/{tax['id']}"
    # Anonymous → 401; editors of the collection may assign.
    assert client.put(url, json={"value_ids": [drift["id"]]}, headers=ANON).status_code == 401
    assigned = client.put(
        url, json={"value_ids": [drift["id"], fordon["id"]]}, headers=_bearer(anna)
    )
    assert assigned.status_code == 200
    assert [v["name"] for v in assigned.json()] == ["Drift", "Transport Modes"]
    # Assignment surfaces on the concept (not the version).
    got = client.get(f"/api/v1/concepts/{concept['id']}").json()
    tx = next(t for t in got["taxonomies"] if t["taxonomy_slug"] == "kategorier")
    assert {v["name"] for v in tx["values"]} == {"Drift", "Transport Modes"}

    # Parts: max_per_concept=1 is HARD.
    parts = client.post(
        "/api/v1/taxonomies",
        json={"slug": "parts", "name": "Delar", "scope": "collection",
              "collection_id": coll["id"], "min_per_concept": 1, "max_per_concept": 1},
        headers=_bearer(anna),
    ).json()
    p1 = _add_value(client, parts["id"], "Del 1 — Common Concepts", _bearer(anna))
    p2 = _add_value(client, parts["id"], "Del 2 — Network", _bearer(anna))
    parts_url = f"/api/v1/concepts/{concept['id']}/taxonomies/{parts['id']}"
    too_many = client.put(
        parts_url, json={"value_ids": [p1["id"], p2["id"]]}, headers=_bearer(anna)
    )
    assert too_many.status_code == 422
    single = client.put(parts_url, json={"value_ids": [p2["id"]]}, headers=_bearer(anna))
    assert single.status_code == 200

    # Replace semantics: assigning a new set replaces the old for THAT taxonomy.
    client.put(url, json={"value_ids": [drift["id"]]}, headers=_bearer(anna))
    got = client.get(f"/api/v1/concepts/{concept['id']}").json()
    tx = next(t for t in got["taxonomies"] if t["taxonomy_slug"] == "kategorier")
    assert [v["name"] for v in tx["values"]] == ["Drift"]
    px = next(t for t in got["taxonomies"] if t["taxonomy_slug"] == "parts")
    assert [v["name"] for v in px["values"]] == ["Del 2 — Network"]

    # Foreign value / wrong-collection taxonomy → 422. (Org-owned: org-less
    # public collections are super-admin-only since the 2026-07 funnel.)
    other_coll = _create_collection(
        client, anna, slug="annan", organisation_id=coll["organisation"]["id"]
    )
    other_concept = _create_concept(
        client, other_coll["id"], form="tur", headers=_bearer(anna)
    ).json()
    assert (
        client.put(
            f"/api/v1/concepts/{other_concept['id']}/taxonomies/{parts['id']}",
            json={"value_ids": [p1["id"]]},
            headers=_bearer(anna),
        ).status_code
        == 422
    )


def test_category_filter_and_categories_on_list_items(client):
    root, anna, coll, concept = _setup(client)
    tax = _global_taxonomy(client, root)
    drift = _add_value(client, tax["id"], "Drift", _bearer(root))
    client.put(
        f"/api/v1/concepts/{concept['id']}/taxonomies/{tax['id']}",
        json={"value_ids": [drift["id"]]},
        headers=_bearer(anna),
    )
    _create_concept(client, coll["id"], form="tur", headers=_bearer(anna))

    hits = client.get("/api/v1/concepts", params={"category": drift["id"]}).json()
    assert [i["canonical_form"] for i in hits["items"]] == ["resa"]
    assert hits["items"][0]["categories"] == ["Drift"]
    # Value deletion cleans up assignments; the filter then matches nothing.
    client.delete(f"/api/v1/taxonomy-values/{drift['id']}", headers=_bearer(root))
    assert client.get("/api/v1/concepts", params={"category": drift["id"]}).json()["total"] == 0


def test_multi_collection_and_multi_tag_filters(client):
    _root, anna, coll, _concept = _setup(client)
    coll2 = _create_collection(
        client, anna, slug="tvaan", organisation_id=coll["organisation"]["id"]
    )
    _create_concept(
        client, coll2["id"], form="biljett", headers=_bearer(anna), tags=["taxa", "resa"]
    )
    _create_concept(
        client, coll2["id"], form="zon", headers=_bearer(anna), tags=["taxa"]
    )

    both = client.get(
        "/api/v1/concepts", params={"collection": f"{coll['slug']},{coll2['slug']}"}
    ).json()
    assert both["total"] == 3
    tagged = client.get("/api/v1/concepts", params={"tag": "resa,zon"}).json()
    assert [i["canonical_form"] for i in tagged["items"]] == ["biljett"]


def test_tags_endpoint_suggests_existing_tags(client):
    _root, anna, coll, _concept = _setup(client)
    _create_concept(
        client, coll["id"], form="biljett", headers=_bearer(anna), tags=["taxa", "biljettsystem"]
    )
    _create_concept(
        client, coll["id"], form="zon", headers=_bearer(anna), tags=["taxa"]
    )
    tags = client.get("/api/v1/tags").json()
    assert tags[0] == {"name": "taxa", "count": 2}
    filtered = client.get("/api/v1/tags", params={"q": "biljett"}).json()
    assert [t["name"] for t in filtered] == ["biljettsystem"]


def test_search_ranking_exact_name_first(client):
    _root, anna, coll, _c = _setup(client)
    _create_concept(client, coll["id"], form="biljettresa", headers=_bearer(anna))
    _create_concept(client, coll["id"], form="biljett", headers=_bearer(anna))
    _create_concept(
        client, coll["id"], form="zon", headers=_bearer(anna),
        definition_md="Gäller som biljett i hela zonen.",
    )
    hits = client.get("/api/v1/concepts", params={"q": "biljett"}).json()
    # Exact name → name-prefix/contains → definition-only.
    assert [i["canonical_form"] for i in hits["items"]] == ["biljett", "biljettresa", "zon"]


def test_taxonomy_values_are_bilingual(client):
    root, _anna, _coll, _c = _setup(client)
    tax = _global_taxonomy(client, root)
    resp = client.post(
        f"/api/v1/taxonomies/{tax['id']}/values",
        json={"name": "Drift", "name_en": "Operations"},
        headers=_bearer(root),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Drift" and resp.json()["name_en"] == "Operations"
