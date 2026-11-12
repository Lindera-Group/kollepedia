"""Begreppssidans omgörning (2026-07): the six ConceptOut counters,
GET /concepts/most-watched (home page), the header bell
(GET /activity/unseen-count, POST /activity/seen), and the history view's
per-row `version_id` + `branch`/`merge` classification (contract §4)."""

from tests.conftest import register_payload

ANON = {"X-User": ""}
PASSWORD = "hemligt-losenord"


def _register(client, handle, password=PASSWORD, display_name=None):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            email=f"{handle}@example.org",
            display_name=display_name or handle.title(),
            password=password,
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _bearer(auth) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['token']}"}


def _create_org(client, auth, slug="k2", name="K2 Nationellt kunskapscentrum"):
    resp = client.post("/api/v1/orgs", json={"name": name, "slug": slug}, headers=_bearer(auth))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_collection(client, auth, slug="min-samling", **overrides):
    payload = {"slug": slug, "name": "Min samling", **overrides}
    resp = client.post("/api/v1/collections", json=payload, headers=_bearer(auth))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_concept(client, collection_id, form="hållplats", headers=None, **kwargs):
    resp = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection_id,
            "canonical_form": form,
            "definition_md": "En definition.",
            **kwargs,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _branch_version(client, concept, headers, name, definition="Förslag."):
    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "branch",
            "branch_name": name,
            "base_version_id": concept["head"]["id"],
            "canonical_form": concept["head"]["canonical_form"],
            "definition_md": definition,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _propose(client, concept_id, headers, branch_name, title="Förbättring"):
    resp = client.post(
        f"/api/v1/concepts/{concept_id}/proposals",
        json={"branch_name": branch_name, "title": title},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------
# 1. ConceptOut's six counters
# --------------------------------------------------------------------------


def test_concept_counters_reflect_engagement(client, collection):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    cesar = _register(client, "cesar")

    concept = _create_concept(client, collection.id, headers=_bearer(anna))

    # watcher_count: two distinct watchers.
    assert (
        client.put(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(bertil)).status_code
        == 204
    )
    assert (
        client.put(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(cesar)).status_code
        == 204
    )

    # list_count: only the CALLER's own pin_lists containing the concept.
    anna_list = client.post(
        "/api/v1/lists", json={"name": "Annas lista"}, headers=_bearer(anna)
    ).json()
    client.post(
        f"/api/v1/lists/{anna_list['id']}/items",
        json={"concept_id": concept["id"], "follow_head": True},
        headers=_bearer(anna),
    )
    bertil_list = client.post(
        "/api/v1/lists", json={"name": "Bertils lista"}, headers=_bearer(bertil)
    ).json()
    client.post(
        f"/api/v1/lists/{bertil_list['id']}/items",
        json={"concept_id": concept["id"], "follow_head": True},
        headers=_bearer(bertil),
    )

    # comment_count excludes proposal threads.
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Kommentar 1"},
        headers=_bearer(bertil),
    )
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Kommentar 2"},
        headers=_bearer(cesar),
    )

    # Two proposals; one gets rejected.
    _branch_version(client, concept, _bearer(bertil), "forslag-a")
    proposal_a = _propose(client, concept["id"], _bearer(bertil), "forslag-a", title="Förslag A")
    client.post(
        f"/api/v1/proposals/{proposal_a['id']}/comments",
        json={"body": "Trådkommentar (ska inte räknas som concept-kommentar)."},
        headers=_bearer(cesar),
    )
    _branch_version(client, concept, _bearer(cesar), "forslag-b")
    proposal_b = _propose(client, concept["id"], _bearer(cesar), "forslag-b", title="Förslag B")
    client.post(
        f"/api/v1/proposals/{proposal_b['id']}/reject",
        json={"note": "Nej tack."},
        headers=_bearer(anna),
    )

    body_anna = client.get(f"/api/v1/concepts/{concept['id']}", headers=_bearer(anna)).json()
    assert body_anna["watcher_count"] == 2
    assert body_anna["list_count"] == 1  # anna's own list only
    assert body_anna["comment_count"] == 2  # excludes the proposal-thread comment
    assert body_anna["proposal_count"] == 2
    assert body_anna["open_proposal_count"] == 1

    body_bertil = client.get(f"/api/v1/concepts/{concept['id']}", headers=_bearer(bertil)).json()
    assert body_bertil["list_count"] == 1  # bertil's own list, not anna's

    body_anon = client.get(f"/api/v1/concepts/{concept['id']}", headers=ANON).json()
    assert body_anon["list_count"] == 0
    # Every other counter is caller-independent.
    assert body_anon["watcher_count"] == body_anna["watcher_count"] == 2
    assert body_anon["comment_count"] == body_anna["comment_count"]
    assert body_anon["proposal_count"] == body_anna["proposal_count"]

    # activity_count reuses the concept's activity feed exactly — an
    # unbounded read of that feed must have exactly that many rows.
    activity = client.get(
        f"/api/v1/concepts/{concept['id']}/activity", params={"limit": 200}
    ).json()
    assert body_anna["activity_count"] == len(activity) > 0


def test_list_count_is_zero_for_anonymous_even_with_watchers(client, collection):
    anna = _register(client, "anna")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    client.put(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(anna))

    body = client.get(f"/api/v1/concepts/{concept['id']}", headers=ANON).json()
    assert body["list_count"] == 0
    assert body["watcher_count"] == 1


# --------------------------------------------------------------------------
# 2. GET /concepts/most-watched
# --------------------------------------------------------------------------


def test_most_watched_orders_by_watcher_count_then_alpha_and_respects_limit(client, collection):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    cesar = _register(client, "cesar")
    diana = _register(client, "diana")
    watchers = [anna, bertil, cesar, diana]

    # "trafik" gets 3 watchers, "resa" gets 3 watchers (tie -> alpha), "buss"
    # gets 1, "ospårad" gets 0 (must be excluded by the >=1 filter).
    trafik = _create_concept(client, collection.id, form="trafik", headers=_bearer(anna))
    resa = _create_concept(client, collection.id, form="resa", headers=_bearer(anna))
    buss = _create_concept(client, collection.id, form="buss", headers=_bearer(anna))
    _create_concept(client, collection.id, form="ospårad", headers=_bearer(anna))

    for user in watchers[:3]:
        client.put(f"/api/v1/concepts/{trafik['id']}/watch", headers=_bearer(user))
    for user in watchers[:3]:
        client.put(f"/api/v1/concepts/{resa['id']}/watch", headers=_bearer(user))
    client.put(f"/api/v1/concepts/{buss['id']}/watch", headers=_bearer(anna))

    items = client.get("/api/v1/concepts/most-watched", headers=ANON).json()
    assert [i["canonical_form"] for i in items] == ["resa", "trafik", "buss"]
    assert [i["watcher_count"] for i in items] == [3, 3, 1]
    assert all(i["watcher_count"] >= 1 for i in items)
    assert items[0]["collection"] == {
        "slug": collection.slug,
        "name": collection.name,
        "year": collection.year,
        "visibility": "public",
        "has_org": False,
    }
    assert items[0]["language"] == "sv"

    limited = client.get(
        "/api/v1/concepts/most-watched", params={"limit": 1}, headers=ANON
    ).json()
    assert len(limited) == 1
    assert limited[0]["canonical_form"] == "resa"


def test_most_watched_hides_org_private_collections_from_outsiders(client):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    org = _create_org(client, anna)
    client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "bertil", "role": "editor"},
        headers=_bearer(anna),
    )
    private = _create_collection(
        client, anna, slug="internt", organisation_id=org["id"], visibility="org_private"
    )
    secret = _create_concept(client, private["id"], form="hemlig-term", headers=_bearer(anna))
    client.put(f"/api/v1/concepts/{secret['id']}/watch", headers=_bearer(anna))
    client.put(f"/api/v1/concepts/{secret['id']}/watch", headers=_bearer(bertil))

    stranger = _register(client, "cesar")
    assert client.get("/api/v1/concepts/most-watched", headers=ANON).json() == []
    assert (
        client.get("/api/v1/concepts/most-watched", headers=_bearer(stranger)).json() == []
    )

    member_view = client.get("/api/v1/concepts/most-watched", headers=_bearer(anna)).json()
    assert [i["canonical_form"] for i in member_view] == ["hemlig-term"]
    assert member_view[0]["watcher_count"] == 2


def test_most_watched_limit_bounds_are_enforced(client, collection):
    assert client.get("/api/v1/concepts/most-watched", params={"limit": 0}).status_code == 422
    assert (
        client.get("/api/v1/concepts/most-watched", params={"limit": 51}).status_code == 422
    )


# --------------------------------------------------------------------------
# 3. Header bell: /activity/unseen-count + /activity/seen
# --------------------------------------------------------------------------


def test_unseen_count_and_seen_require_auth(client):
    assert client.get("/api/v1/activity/unseen-count", headers=ANON).status_code == 401
    assert client.post("/api/v1/activity/seen", headers=ANON).status_code == 401


def test_unseen_count_counts_watched_activity_and_seen_resets_it(client, collection):
    anna = _register(client, "anna")
    diana = _register(client, "diana")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    other = _create_concept(client, collection.id, form="oövervakad", headers=_bearer(anna))

    # NULL activity_seen_at ⇒ everything counts, but only on watched concepts.
    client.put(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(diana))
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Hej diana."},
        headers=_bearer(anna),
    )
    client.post(
        f"/api/v1/concepts/{other['id']}/comments",
        json={"body": "Brus i en obevakad term."},
        headers=_bearer(anna),
    )

    before = client.get("/api/v1/activity/unseen-count", headers=_bearer(diana)).json()
    # The concept's own creation version + the one comment on the watched
    # concept — never the comment on the unwatched one.
    assert before["count"] == 2

    assert client.post("/api/v1/activity/seen", headers=_bearer(diana)).status_code == 204
    after_seen = client.get("/api/v1/activity/unseen-count", headers=_bearer(diana)).json()
    assert after_seen["count"] == 0

    # A fresh event after the mark-seen instant is unseen again.
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Ny signal."},
        headers=_bearer(anna),
    )
    after_new_event = client.get("/api/v1/activity/unseen-count", headers=_bearer(diana)).json()
    assert after_new_event["count"] == 1


def test_unseen_count_ignores_concepts_the_caller_no_longer_watches(client, collection):
    anna = _register(client, "anna")
    diana = _register(client, "diana")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))

    assert client.get("/api/v1/activity/unseen-count", headers=_bearer(diana)).json() == {
        "count": 0
    }
    client.put(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(diana))
    client.delete(f"/api/v1/concepts/{concept['id']}/watch", headers=_bearer(diana))
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Efter unwatch."},
        headers=_bearer(anna),
    )
    assert client.get("/api/v1/activity/unseen-count", headers=_bearer(diana)).json() == {
        "count": 0
    }


# --------------------------------------------------------------------------
# 4. History view's event layer: version_id + branch/merge classification
# --------------------------------------------------------------------------


def _activity_for(client, concept_id):
    return client.get(
        f"/api/v1/concepts/{concept_id}/activity", params={"limit": 200}
    ).json()


def test_fast_forward_proposal_merge_is_a_merge_event(client, collection):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    branched = _branch_version(client, concept, _bearer(bertil), "forslag")
    proposal = _propose(client, concept["id"], _bearer(bertil), "forslag")

    merge_resp = client.post(
        f"/api/v1/proposals/{proposal['id']}/merge",
        json={"note": "Ser bra ut."},
        headers=_bearer(anna),
    )
    assert merge_resp.status_code == 200

    items = _activity_for(client, concept["id"])
    kinds = {i["kind"] for i in items}
    assert "branch" in kinds
    assert "merge" in kinds
    branch_row = next(i for i in items if i["kind"] == "branch")
    assert branch_row["version_id"] == branched["id"]
    merge_row = next(i for i in items if i["kind"] == "merge")
    assert merge_row["version_id"] != branched["id"]  # the merge's own (new) version
    merged_row = next(i for i in items if i["kind"] == "proposal_merged")
    assert merged_row["version_id"] == branched["id"]  # the proposal's source-branch head


def test_merge_of_endorsed_source_head_defaults_to_proposed(client, collection):
    """'endorsed' is no longer a status — a legacy payload coerces to
    'proposed' at creation (graph.coerce_status), so the merged head can
    never carry it either."""
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    branched = _branch_version(client, concept, _bearer(bertil), "forslag")
    endorsed = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": branched["id"],
            "canonical_form": branched["canonical_form"],
            "definition_md": "Fastställd grentext.",
            "status": "endorsed",
        },
        headers=_bearer(bertil),
    )
    assert endorsed.status_code == 201, endorsed.text

    proposal = _propose(client, concept["id"], _bearer(bertil), "forslag")
    merge_resp = client.post(
        f"/api/v1/proposals/{proposal['id']}/merge",
        json={"note": "In med den."},
        headers=_bearer(anna),
    )
    assert merge_resp.status_code == 200, merge_resp.text

    head = client.get(f"/api/v1/concepts/{concept['id']}").json()["head"]
    assert head["status"] == "proposed"


def test_non_fast_forward_proposal_merge_is_a_merge_event(client, collection):
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    branched = _branch_version(client, concept, _bearer(bertil), "forslag")
    proposal = _propose(client, concept["id"], _bearer(bertil), "forslag")

    # Main moves on before the merge — forces the synthesize path.
    client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": concept["head"]["canonical_form"],
            "definition_md": "Huvudgrenen gick vidare under tiden.",
        },
        headers=_bearer(anna),
    )
    merge_resp = client.post(
        f"/api/v1/proposals/{proposal['id']}/merge",
        json={"note": "Slår ihop."},
        headers=_bearer(anna),
    )
    assert merge_resp.status_code == 200

    items = _activity_for(client, concept["id"])
    merge_rows = [i for i in items if i["kind"] == "merge"]
    assert len(merge_rows) == 1
    assert merge_rows[0]["version_id"] not in (branched["id"], concept["head"]["id"])


def test_manual_synthesize_is_a_merge_event(client, collection):
    anna = _register(client, "anna")
    root = _create_concept(client, collection.id, form="resa", headers=_bearer(anna))
    other = _create_concept(client, collection.id, form="tur", headers=_bearer(anna))

    resp = client.post(
        f"/api/v1/concepts/{root['id']}/versions",
        json={
            "mode": "synthesize",
            "base_version_id": root["head"]["id"],
            "extra_parent_ids": [other["head"]["id"]],
            "canonical_form": "resa",
            "definition_md": "Sammanslagen definition.",
        },
        headers=_bearer(anna),
    )
    assert resp.status_code == 201
    synthesized = resp.json()

    items = _activity_for(client, root["id"])
    merge_row = next(i for i in items if i["kind"] == "merge")
    assert merge_row["version_id"] == synthesized["id"]


def test_comment_rows_have_null_version_id_and_endorsement_rows_have_the_endorsed_version(
    client, collection
):
    root = _register(client, "root")
    anna = _register(client, "anna")
    _create_org(client, anna)
    client.post("/api/v1/orgs/k2/approve", headers=_bearer(root))
    concept = _create_concept(client, collection.id, headers=_bearer(anna))
    stamped = client.post(
        f"/api/v1/versions/{concept['head']['id']}/endorsements",
        json={"note": "Fastställd."},
        headers=_bearer(anna),
    )
    assert stamped.status_code == 201, stamped.text
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "En kommentar."},
        headers=_bearer(anna),
    )

    items = _activity_for(client, concept["id"])
    comment_row = next(i for i in items if i["kind"] == "comment")
    assert comment_row["version_id"] is None
    endorsement_row = next(i for i in items if i["kind"] == "endorsement")
    assert endorsement_row["version_id"] == concept["head"]["id"]
    for row in items:
        assert row["kind"] and row["at"] and row["summary"] is not None
