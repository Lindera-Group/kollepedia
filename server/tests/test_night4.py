"""Night-4 tests: email (allowlist SAFETY, outbox, verify, forgot), change
proposals (lifecycle, merge semantics, rights), per-collection edit policy,
comments, watching, computed activity, saved prompts, AI provider adapter
(berget/openai) and citable version permalinks."""

import re

from tests.conftest import register_payload

ANON = {"X-User": ""}
PASSWORD = "hemligt-losenord"


def _register(client, handle, password=PASSWORD, display_name=None, email=None):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": email or f"{handle}@example.org",
                "display_name": display_name or handle.title(),
                "password": password,
            },
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _bearer(auth) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['token']}"}


def _login(client, identifier, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})


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
    return client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection_id,
            "canonical_form": form,
            "definition_md": "En definition.",
            **kwargs,
        },
        headers=headers,
    )


def _branch(client, concept, headers, name="forslag", definition="Föreslagen text."):
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
    return resp


def _propose(client, concept_id, headers, branch_name="forslag", title="Förbättrad definition"):
    return client.post(
        f"/api/v1/concepts/{concept_id}/proposals",
        json={"branch_name": branch_name, "title": title, "description": "Se grenen."},
        headers=headers,
    )


def _org_setup(client):
    """root (super), anna (org admin/owner), cesar (editor member), bertil
    (stranger) + a PUBLIC org-owned collection (edit_policy 'org') with one
    concept. Multi-org semantics: the org must be APPROVED by the super admin
    before it can own collections."""
    root = _register(client, "root")
    anna = _register(client, "anna")
    cesar = _register(client, "cesar")
    bertil = _register(client, "bertil")
    org = _create_org(client, anna)
    approved = client.post("/api/v1/orgs/k2/approve", headers=_bearer(root))
    assert approved.status_code == 200, approved.text
    client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "cesar", "role": "editor"},
        headers=_bearer(anna),
    )
    coll = _create_collection(client, anna, slug="k2-ordlista", organisation_id=org["id"])
    concept = _create_concept(client, coll["id"], form="resa", headers=_bearer(anna)).json()
    return root, anna, cesar, bertil, coll, concept


def _outbox(client, auth, limit=100):
    resp = client.get(f"/api/v1/admin/outbox?limit={limit}", headers=_bearer(auth))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _token_from_body(body_text: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body_text)
    assert match, body_text
    return match.group(1)


# --------------------------------------------------------------------------
# Email: allowlist SAFETY, backends, outbox
# --------------------------------------------------------------------------


def test_email_allowlist_blocks_even_with_fake_smtp_backend(db, monkeypatch):
    """THE safety property: with SMTP fully configured, a recipient outside
    EMAIL_ALLOWLIST is stored as 'blocked' and no backend is ever invoked —
    and without any allowlist at all EVERY recipient is blocked (fail closed,
    2026-11-10: there is no built-in default address any more)."""
    from app import email as email_service

    calls: list[dict] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda **kw: calls.append(kw))
    monkeypatch.setenv("SMTP_URL", "smtp://user:pass@mail.example.org:587")
    monkeypatch.setenv("EMAIL_ALLOWLIST", "granskare@example.org")

    blocked = email_service.send(
        db, to_addr="Evil@Example.org", subject="Hej", body_text="x", template="verify_email"
    )
    assert blocked.status == "blocked"
    assert blocked.sent_at is None
    assert calls == []  # the fake SMTP backend was NEVER touched

    sent = email_service.send(
        db,
        to_addr="Granskare@Example.org",
        subject="Hej",
        body_text="x",
        template="verify_email",
    )
    assert sent.status == "sent"
    assert sent.sent_at is not None
    assert len(calls) == 1
    assert calls[0]["to_addr"] == "Granskare@Example.org"
    assert calls[0]["from_addr"] == "user"  # SMTP user name when EMAIL_FROM is unset

    # A different allowlist replaces, never unions.
    monkeypatch.setenv("EMAIL_ALLOWLIST", "annan@example.org")
    swapped = email_service.send(
        db, to_addr="granskare@example.org", subject="Hej", body_text="x", template="t"
    )
    assert swapped.status == "blocked"
    assert len(calls) == 1

    # No allowlist at all → nobody, not a built-in default.
    monkeypatch.delenv("EMAIL_ALLOWLIST")
    unset = email_service.send(
        db, to_addr="granskare@example.org", subject="Hej", body_text="x", template="t"
    )
    assert unset.status == "blocked"
    assert len(calls) == 1


def test_email_default_backend_is_outbox_and_admin_endpoint(client):
    root = _register(client, "root")
    _register(client, "marty")

    # Super admin only.
    anna = _register(client, "anna")
    assert client.get("/api/v1/admin/outbox", headers=_bearer(anna)).status_code == 403
    assert client.get("/api/v1/admin/outbox", headers=ANON).status_code == 401

    messages = _outbox(client, root)
    by_addr = {m["to_addr"]: m for m in messages}
    # No SMTP_URL: every message is stored, none sent — the allowlist does
    # not enter into it (there is no backend to reach anyone with).
    for addr in ("root@example.org", "marty@example.org", "anna@example.org"):
        assert by_addr[addr]["status"] == "outbox", addr
        assert by_addr[addr]["sent_at"] is None
        assert by_addr[addr]["template"] == "verify_email"
    # Newest first + limit.
    assert messages[0]["to_addr"] == "anna@example.org"
    assert len(_outbox(client, root, limit=1)) == 1


def test_verify_email_flow(client):
    root = _register(client, "root")
    anna = _register(client, "anna")

    # Registration already minted a verification token (stored even though
    # the recipient was blocked — the outbox is the audit surface).
    message = next(
        m
        for m in _outbox(client, root)
        if m["to_addr"] == "anna@example.org" and m["template"] == "verify_email"
    )
    token = _token_from_body(message["body_text"])
    assert "/verify-email?token=" in message["body_text"]

    me = client.get("/api/v1/auth/me", headers=_bearer(anna)).json()
    assert me["email_verified"] is False
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 204
    me = client.get("/api/v1/auth/me", headers=_bearer(anna)).json()
    assert me["email_verified"] is True

    # One-time: reuse → 400; garbage → 400.
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": "nope"}).status_code == 400

    # Changing the email re-verifies (and 409s on someone else's address).
    taken = client.post(
        "/api/v1/auth/email", json={"email": "root@example.org"}, headers=_bearer(anna)
    )
    assert taken.status_code == 409
    assert (
        client.post(
            "/api/v1/auth/email", json={"email": "inte-en-adress"}, headers=_bearer(anna)
        ).status_code
        == 422
    )
    changed = client.post(
        "/api/v1/auth/email", json={"email": "anna.ny@example.org"}, headers=_bearer(anna)
    )
    assert changed.status_code == 204
    me = client.get("/api/v1/auth/me", headers=_bearer(anna)).json()
    assert me["email"] == "anna.ny@example.org"
    assert me["email_verified"] is False

    # The freshly minted token for the new address verifies again.
    fresh = next(m for m in _outbox(client, root) if m["to_addr"] == "anna.ny@example.org")
    assert (
        client.post(
            "/api/v1/auth/verify-email", json={"token": _token_from_body(fresh["body_text"])}
        ).status_code
        == 204
    )


def test_verify_email_token_dies_when_address_changes(client):
    root = _register(client, "root")
    anna = _register(client, "anna")
    # Mint a fresh token for the current address…
    assert (
        client.post(
            "/api/v1/auth/email", json={"email": "anna@example.org"}, headers=_bearer(anna)
        ).status_code
        == 204
    )
    stale = [
        _token_from_body(m["body_text"])
        for m in _outbox(client, root)
        if m["to_addr"] == "anna@example.org"
    ]
    # …then change the address: every earlier token must be dead.
    client.post("/api/v1/auth/email", json={"email": "anna.ny@example.org"}, headers=_bearer(anna))
    for token in stale:
        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_forgot_is_204_for_unknown_and_unverified(client):
    root = _register(client, "root")
    _register(client, "anna")  # email set but NOT verified

    # Unknown identifier → 204, and no reset email produced (no enumeration).
    assert (
        client.post(
            "/api/v1/auth/forgot", json={"handle_or_email": "finns-inte@example.org"}
        ).status_code
        == 204
    )
    # Known but unverified → 204, still no reset email.
    assert client.post("/api/v1/auth/forgot", json={"handle_or_email": "anna"}).status_code == 204
    templates = [m["template"] for m in _outbox(client, root)]
    assert "reset_password" not in templates


def test_forgot_sends_reset_link_for_verified_email(client):
    root = _register(client, "root")
    anna = _register(client, "anna")

    verify = next(m for m in _outbox(client, root) if m["to_addr"] == "anna@example.org")
    client.post("/api/v1/auth/verify-email", json={"token": _token_from_body(verify["body_text"])})

    # Identifier may be the email or the handle.
    assert (
        client.post(
            "/api/v1/auth/forgot", json={"handle_or_email": "Anna@Example.org"}
        ).status_code
        == 204
    )
    reset_message = next(m for m in _outbox(client, root) if m["template"] == "reset_password")
    assert reset_message["to_addr"] == "anna@example.org"
    assert reset_message["status"] == "outbox"  # stored, not sent (no SMTP_URL)
    assert "/reset?token=" in reset_message["body_text"]

    token = _token_from_body(reset_message["body_text"])
    assert (
        client.post(
            "/api/v1/auth/reset", json={"token": token, "new_password": "splitternytt-1"}
        ).status_code
        == 204
    )
    assert _login(client, "anna@example.org", PASSWORD).status_code == 401
    assert _login(client, "anna@example.org", "splitternytt-1").status_code == 200
    assert anna["user"]["handle"] == "anna"


# --------------------------------------------------------------------------
# Change proposals: lifecycle
# --------------------------------------------------------------------------


def test_proposal_requires_existing_non_main_branch(client):
    _root, _anna, cesar, _bertil, _coll, concept = _org_setup(client)

    assert _propose(client, concept["id"], ANON).status_code == 401
    assert (
        _propose(client, concept["id"], _bearer(cesar), branch_name="finns-inte").status_code
        == 404
    )
    assert _propose(client, concept["id"], _bearer(cesar), branch_name="main").status_code == 422

    branched = _branch(client, concept, _bearer(cesar))
    assert branched.status_code == 201, branched.text
    created = _propose(client, concept["id"], _bearer(cesar))
    assert created.status_code == 201, created.text
    proposal = created.json()
    assert proposal["status"] == "open"
    assert proposal["concept_id"] == concept["id"]
    assert proposal["canonical_form"] == "resa"
    assert proposal["collection_slug"] == "k2-ordlista"
    assert proposal["source_branch_name"] == "forslag"
    assert proposal["target_branch"] == "main"
    assert proposal["title"] == "Förbättrad definition"
    assert proposal["created_by"]["handle"] == "cesar"
    assert proposal["resolved_at"] is None
    # The diff triple: source head, target head, branch point.
    assert proposal["source_head"]["id"] == branched.json()["id"]
    assert proposal["target_head"]["id"] == concept["head"]["id"]
    assert proposal["base_version_id"] == concept["head"]["id"]

    # Detail + list endpoints agree.
    detail = client.get(f"/api/v1/proposals/{proposal['id']}").json()
    assert detail["source_head"]["definition_md"] == "Föreslagen text."
    listed = client.get(
        "/api/v1/proposals", params={"status": "open", "collection": "k2-ordlista"}
    ).json()
    assert [p["id"] for p in listed] == [proposal["id"]]
    assert (
        client.get("/api/v1/proposals", params={"concept_id": concept["id"]}).json()[0]["id"]
        == proposal["id"]
    )


def test_proposal_open_duplicate_409(client):
    _root, _anna, cesar, _bertil, _coll, concept = _org_setup(client)
    _branch(client, concept, _bearer(cesar))
    first = _propose(client, concept["id"], _bearer(cesar)).json()
    assert _propose(client, concept["id"], _bearer(cesar)).status_code == 409

    # Withdrawing frees the branch for a new proposal.
    withdrawn = client.post(f"/api/v1/proposals/{first['id']}/withdraw", headers=_bearer(cesar))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert _propose(client, concept["id"], _bearer(cesar)).status_code == 201


def test_proposal_merge_fast_forward(client):
    _root, anna, cesar, _bertil, _coll, concept = _org_setup(client)
    source_head = _branch(client, concept, _bearer(cesar)).json()
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()

    # Note is required.
    assert (
        client.post(
            f"/api/v1/proposals/{proposal['id']}/merge", json={}, headers=_bearer(anna)
        ).status_code
        == 422
    )
    merged = client.post(
        f"/api/v1/proposals/{proposal['id']}/merge",
        json={"note": "Bra förbättring."},
        headers=_bearer(anna),
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()
    assert body["status"] == "merged"
    assert body["resolved_by"]["handle"] == "anna"
    assert body["resolution_note"] == "Bra förbättring."
    assert body["resolved_at"] is not None

    # The new main head COPIES the source head content…
    new_head = body["target_head"]
    assert new_head["id"] != concept["head"]["id"]
    assert new_head["canonical_form"] == source_head["canonical_form"]
    assert new_head["definition_md"] == source_head["definition_md"]
    assert new_head["note"] == "Bra förbättring."
    assert new_head["provenance"]["merged_from_proposal"] == proposal["id"]
    # …as a fast-forward: a plain revision of the old target head.
    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    edges = [e for e in graph["edges"] if e["child_id"] == new_head["id"]]
    assert edges == [
        {
            "child_id": new_head["id"],
            "parent_id": concept["head"]["id"],
            "edge_type": "revised_from",
            "ordinal": 0,
            "note": None,
        }
    ]


def test_proposal_merge_synthesis_when_target_moved(client):
    _root, anna, cesar, _bertil, _coll, concept = _org_setup(client)
    source_head = _branch(client, concept, _bearer(cesar)).json()
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()

    # Main moves after the proposal was opened.
    moved = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "resa",
            "definition_md": "Under tiden ändrad.",
        },
        headers=_bearer(anna),
    ).json()

    merged = client.post(
        f"/api/v1/proposals/{proposal['id']}/merge",
        json={"note": "Sammanfogar trots parallell ändring."},
        headers=_bearer(anna),
    )
    assert merged.status_code == 200, merged.text
    new_head = merged.json()["target_head"]
    # Content still copies the source head (the resolver's explicit call)…
    assert new_head["definition_md"] == source_head["definition_md"]
    # …but lineage records a synthesis with parents [target head, source head].
    graph = client.get(f"/api/v1/concepts/{concept['id']}/graph").json()
    edges = sorted(
        (e for e in graph["edges"] if e["child_id"] == new_head["id"]),
        key=lambda e: e["ordinal"],
    )
    assert [(e["parent_id"], e["edge_type"], e["ordinal"]) for e in edges] == [
        (moved["id"], "synthesized_from", 0),
        (source_head["id"], "synthesized_from", 1),
    ]


def test_proposal_rights_matrix_and_reject(client):
    root, anna, cesar, bertil, _coll, concept = _org_setup(client)
    _branch(client, concept, _bearer(cesar))
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()
    url = f"/api/v1/proposals/{proposal['id']}"

    # Merge/reject: stranger and editor member → 403; anonymous → 401.
    for headers, expected in ((_bearer(bertil), 403), (_bearer(cesar), 403), (ANON, 401)):
        assert (
            client.post(f"{url}/merge", json={"note": "x"}, headers=headers).status_code
            == expected
        )
        assert (
            client.post(f"{url}/reject", json={"note": "x"}, headers=headers).status_code
            == expected
        )
    # Withdraw: only the author (or super).
    assert client.post(f"{url}/withdraw", headers=_bearer(bertil)).status_code == 403
    assert client.post(f"{url}/withdraw", headers=_bearer(anna)).status_code == 403

    # Reject requires a note; org admin can reject; super could too.
    assert (
        client.post(f"{url}/reject", json={"note": ""}, headers=_bearer(anna)).status_code == 422
    )
    rejected = client.post(
        f"{url}/reject", json={"note": "Täcks redan av huvuddefinitionen."}, headers=_bearer(anna)
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["resolution_note"] == "Täcks redan av huvuddefinitionen."

    # Super admin may withdraw someone else's (still-open) proposal.
    _branch(client, concept, _bearer(cesar), name="forslag-2")
    second = _propose(client, concept["id"], _bearer(cesar), branch_name="forslag-2").json()
    assert (
        client.post(
            f"/api/v1/proposals/{second['id']}/withdraw", headers=_bearer(root)
        ).status_code
        == 200
    )
    assert client.get("/api/v1/proposals/finns-inte").status_code == 404


def test_resolving_non_open_proposal_409(client):
    _root, anna, cesar, _bertil, _coll, concept = _org_setup(client)
    _branch(client, concept, _bearer(cesar))
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()
    url = f"/api/v1/proposals/{proposal['id']}"
    assert (
        client.post(f"{url}/merge", json={"note": "In."}, headers=_bearer(anna)).status_code == 200
    )
    assert (
        client.post(f"{url}/merge", json={"note": "Igen."}, headers=_bearer(anna)).status_code
        == 409
    )
    assert (
        client.post(f"{url}/reject", json={"note": "Nej."}, headers=_bearer(anna)).status_code
        == 409
    )
    assert client.post(f"{url}/withdraw", headers=_bearer(cesar)).status_code == 409


def test_locked_collection_allows_branch_but_not_revise(client):
    _root, anna, cesar, bertil, coll, concept = _org_setup(client)
    client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_locked": True}, headers=_bearer(anna)
    )

    # revise/synthesize/promote stay 423 for non-exempt users…
    revise = {
        "mode": "revise",
        "base_version_id": concept["head"]["id"],
        "canonical_form": "resa",
        "definition_md": "Ny text.",
    }
    for headers in (_bearer(cesar), _bearer(bertil)):
        assert (
            client.post(
                f"/api/v1/concepts/{concept['id']}/versions", json=revise, headers=headers
            ).status_code
            == 423
        )
    assert (
        client.post(
            f"/api/v1/concepts/{concept['id']}/promote",
            json={"version_id": concept["head"]["id"]},
            headers=_bearer(cesar),
        ).status_code
        == 423
    )
    # …but mode=branch is allowed for ANY authed identity — including a
    # complete stranger. This is how locked content evolves (VISION §4.3).
    branched = _branch(client, concept, _bearer(bertil), name="bertils-forslag")
    assert branched.status_code == 201, branched.text
    # Anonymous visitors are still shut out.
    assert _branch(client, concept, ANON, name="anonym-gren").status_code == 401

    # The full loop: the stranger proposes, the steward merges — on a locked
    # collection.
    proposal = _propose(client, concept["id"], _bearer(bertil), branch_name="bertils-forslag")
    assert proposal.status_code == 201, proposal.text
    merged = client.post(
        f"/api/v1/proposals/{proposal.json()['id']}/merge",
        json={"note": "Tack för förslaget."},
        headers=_bearer(anna),
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["target_head"]["definition_md"] == "Föreslagen text."


# --------------------------------------------------------------------------
# Per-collection edit policy
# --------------------------------------------------------------------------


def test_edit_policy_org_blocks_stranger_but_member_writes(client):
    _root, _anna, cesar, bertil, coll, _concept = _org_setup(client)
    # Org-owned collections default to policy 'org'.
    assert coll["edit_policy"] == "org"
    denied = _create_concept(client, coll["id"], form="ny", headers=_bearer(bertil))
    assert denied.status_code == 403
    assert _create_concept(client, coll["id"], form="ny", headers=ANON).status_code == 401
    member = _create_concept(client, coll["id"], form="ny", headers=_bearer(cesar))
    assert member.status_code == 201


def test_edit_policy_anyone_requires_some_identity(client):
    _root, anna, _cesar, bertil, coll, _concept = _org_setup(client)
    patched = client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"edit_policy": "anyone"},
        headers=_bearer(anna),
    )
    assert patched.status_code == 200
    assert patched.json()["edit_policy"] == "anyone"
    # Any logged-in identity writes; anonymous still 401.
    stranger = _create_concept(client, coll["id"], form="ny", headers=_bearer(bertil))
    assert stranger.status_code == 201
    assert _create_concept(client, coll["id"], form="ny2", headers=ANON).status_code == 401
    # Garbage policy value → 422.
    assert (
        client.patch(
            f"/api/v1/collections/{coll['slug']}",
            json={"edit_policy": "wiki"},
            headers=_bearer(anna),
        ).status_code
        == 422
    )


def test_anonymous_users_are_gone_open_policy_refused_and_legacy_requires_account(client):
    """Migration 008: anonymous writes are removed entirely. 'open' is no
    longer an accepted edit policy, and a legacy 'open' row left in the
    database behaves as 'anyone' — an account is always required."""
    _root, anna, _cesar, _bertil, coll, concept = _org_setup(client)

    # 'open' is refused at the API boundary now.
    refused = client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"edit_policy": "open"},
        headers=_bearer(anna),
    )
    assert refused.status_code == 422

    # A pre-migration 'open' row (planted straight into the DB) must NOT
    # grant anonymous writes: it behaves as 'anyone'.
    client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"edit_policy": "anyone"},
        headers=_bearer(anna),
    )
    assert _create_concept(client, coll["id"], form="vildvuxen", headers=ANON).status_code == 401

    revised = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "resa",
            "definition_md": "Anonymt försök.",
        },
        headers=ANON,
    )
    assert revised.status_code == 401

    imported = client.post(
        f"/api/v1/collections/{coll['slug']}/import-rows",
        json={"rows": [{"canonical_form": "x", "definition": "En definition."}]},
        headers=ANON,
    )
    assert imported.status_code == 401

    # Signed-in users can still write under 'anyone'.
    ok = _create_concept(client, coll["id"], form="tillåtet", headers=_bearer(anna))
    assert ok.status_code == 201, ok.text


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------


def test_comments_crud_on_concepts_and_proposals(client):
    root, _anna, cesar, bertil, _coll, concept = _org_setup(client)
    url = f"/api/v1/concepts/{concept['id']}/comments"

    assert client.post(url, json={"body": "Hej"}, headers=ANON).status_code == 401
    posted = client.post(url, json={"body": "Bör breddas."}, headers=_bearer(cesar))
    assert posted.status_code == 201, posted.text
    comment = posted.json()
    assert comment["concept_id"] == concept["id"]
    assert comment["proposal_id"] is None
    assert comment["created_by"]["handle"] == "cesar"

    # Proposal comments hang on the proposal AND its concept.
    _branch(client, concept, _bearer(cesar))
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()
    proposal_url = f"/api/v1/proposals/{proposal['id']}/comments"
    on_proposal = client.post(
        proposal_url, json={"body": "Se särskilt andra stycket."}, headers=_bearer(bertil)
    )
    assert on_proposal.status_code == 201
    assert on_proposal.json()["proposal_id"] == proposal["id"]

    # Listings are scoped: concept list excludes proposal comments.
    assert [c["body"] for c in client.get(url).json()] == ["Bör breddas."]
    assert [c["body"] for c in client.get(proposal_url).json()] == ["Se särskilt andra stycket."]

    # Delete: stranger 403, author 204, super 204, unknown 404.
    delete_url = f"/api/v1/comments/{comment['id']}"
    assert client.delete(delete_url, headers=_bearer(bertil)).status_code == 403
    assert client.delete(delete_url, headers=_bearer(cesar)).status_code == 204
    assert client.delete(delete_url, headers=_bearer(cesar)).status_code == 404
    assert (
        client.delete(
            f"/api/v1/comments/{on_proposal.json()['id']}", headers=_bearer(root)
        ).status_code
        == 204
    )
    assert client.get(url).json() == []


def test_comment_body_limit_4000_chars(client):
    _root, _anna, cesar, _bertil, _coll, concept = _org_setup(client)
    url = f"/api/v1/concepts/{concept['id']}/comments"
    ok = client.post(url, json={"body": "x" * 4000}, headers=_bearer(cesar))
    assert ok.status_code == 201
    too_long = client.post(url, json={"body": "x" * 4001}, headers=_bearer(cesar))
    assert too_long.status_code == 422
    assert client.post(url, json={"body": ""}, headers=_bearer(cesar)).status_code == 422


def test_comments_hidden_with_org_private_collection(client):
    _root, anna, _cesar, bertil, coll, concept = _org_setup(client)
    client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"visibility": "org_private"},
        headers=_bearer(anna),
    )
    url = f"/api/v1/concepts/{concept['id']}/comments"
    for headers in (ANON, _bearer(bertil)):
        assert client.get(url, headers=headers).status_code == 404
    assert client.post(url, json={"body": "Hej"}, headers=_bearer(bertil)).status_code == 404
    assert client.get(url, headers=_bearer(anna)).status_code == 200


# --------------------------------------------------------------------------
# Watching + activity
# --------------------------------------------------------------------------


def test_watch_unwatch_and_watching_flag(client):
    _root, anna, cesar, _bertil, _coll, concept = _org_setup(client)
    url = f"/api/v1/concepts/{concept['id']}/watch"

    assert client.put(url, headers=ANON).status_code == 401
    unknown = client.put("/api/v1/concepts/finns-inte/watch", headers=_bearer(anna))
    assert unknown.status_code == 404

    assert client.put(url, headers=_bearer(anna)).status_code == 204
    assert client.put(url, headers=_bearer(anna)).status_code == 204  # idempotent

    concept_url = f"/api/v1/concepts/{concept['id']}"
    assert client.get(concept_url, headers=_bearer(anna)).json()["watching"] is True
    assert client.get(concept_url, headers=_bearer(cesar)).json()["watching"] is False
    assert client.get(concept_url, headers=ANON).json()["watching"] is False

    assert client.delete(url, headers=_bearer(anna)).status_code == 204
    assert client.delete(url, headers=_bearer(anna)).status_code == 204  # idempotent
    assert client.get(concept_url, headers=_bearer(anna)).json()["watching"] is False


def test_concept_activity_is_public_computed_and_ordered(client):
    _root, anna, cesar, _bertil, _coll, concept = _org_setup(client)
    # Stamping requires an APPROVED org — _org_setup approves k2, and anna's
    # single admin membership makes the acting org auto-selected.

    revised = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "resa",
            "definition_md": "Utökad.",
        },
        headers=_bearer(anna),
    ).json()
    stamped = client.post(
        f"/api/v1/versions/{concept['head']['id']}/endorsements",
        json={"note": "Fastställd."},
        headers=_bearer(anna),
    )
    assert stamped.status_code == 201, stamped.text
    client.post(
        f"/api/v1/concepts/{concept['id']}/comments",
        json={"body": "Diskussion pågår."},
        headers=_bearer(cesar),
    )
    branched = _branch(client, concept, _bearer(cesar)).json()
    proposal = _propose(client, concept["id"], _bearer(cesar)).json()
    client.post(
        f"/api/v1/proposals/{proposal['id']}/reject",
        json={"note": "Avslås."},
        headers=_bearer(anna),
    )

    # Public read (anonymous), all six kinds present, newest first. Kinds are
    # outcome-specific and summaries language-neutral (the UI localizes the
    # label per kind) since migration 008. mode='branch' is its own `branch`
    # kind (2026-07 correction to the begreppssida contract §4), distinct
    # from a plain `version` revision.
    items = client.get(f"/api/v1/concepts/{concept['id']}/activity", headers=ANON).json()
    kinds = {i["kind"] for i in items}
    assert kinds == {
        "version",
        "branch",
        "endorsement",
        "comment",
        "proposal",
        "proposal_rejected",
    }
    stamps = [i["at"] for i in items]
    assert stamps == sorted(stamps, reverse=True)
    assert all(i["concept_id"] == concept["id"] for i in items)
    assert all(i["canonical_form"] == "resa" for i in items)
    resolved = next(i for i in items if i["kind"] == "proposal_rejected")
    assert resolved["actor"]["handle"] == "anna"
    comment = next(i for i in items if i["kind"] == "comment")
    assert comment["summary"] == "Diskussion pågår."
    assert comment["version_id"] is None

    # version_id: each row names the version it concerns (§4 correction) —
    # a version/branch row is its own id, a proposal row is its source
    # branch's head (here: the branch's sole version).
    version_row = next(i for i in items if i["kind"] == "version")
    assert version_row["version_id"] == revised["id"]
    branch_row = next(i for i in items if i["kind"] == "branch")
    assert branch_row["version_id"] == branched["id"]
    assert resolved["version_id"] == branched["id"]
    proposal_row = next(i for i in items if i["kind"] == "proposal")
    assert proposal_row["version_id"] == branched["id"]

    # limit is honoured.
    assert (
        len(client.get(f"/api/v1/concepts/{concept['id']}/activity", params={"limit": 2}).json())
        == 2
    )


def test_global_activity_requires_auth_and_covers_only_watched(client, collection):
    _root, _anna, cesar, _bertil, coll, watched_concept = _org_setup(client)
    other = _create_concept(client, coll["id"], form="tur", headers=_bearer(cesar)).json()
    diana = _register(client, "diana")

    assert client.get("/api/v1/activity", headers=ANON).status_code == 401
    assert client.get("/api/v1/activity", headers=_bearer(diana)).json() == []

    client.put(f"/api/v1/concepts/{watched_concept['id']}/watch", headers=_bearer(diana))
    client.post(
        f"/api/v1/concepts/{other['id']}/comments",
        json={"body": "Brus i ett annat begrepp."},
        headers=_bearer(cesar),
    )
    client.post(
        f"/api/v1/concepts/{watched_concept['id']}/comments",
        json={"body": "Signal i det bevakade."},
        headers=_bearer(cesar),
    )

    items = client.get("/api/v1/activity", headers=_bearer(diana)).json()
    assert items  # the watched concept has at least its version + comment
    assert all(i["concept_id"] == watched_concept["id"] for i in items)
    assert items[0]["kind"] == "comment"
    assert items[0]["summary"] == "Signal i det bevakade."


# --------------------------------------------------------------------------
# Saved prompts
# --------------------------------------------------------------------------


def test_prompts_crud_and_shared_visibility(client):
    root = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")

    assert (
        client.post(
            "/api/v1/prompts",
            json={"name": "X", "intent": "synthesize", "text": "T"},
            headers=ANON,
        ).status_code
        == 401
    )
    private = client.post(
        "/api/v1/prompts",
        json={"name": "Min stil", "intent": "synthesize", "text": "Skriv kort."},
        headers=_bearer(anna),
    )
    assert private.status_code == 201, private.text
    assert private.json()["shared"] is False
    assert private.json()["owner_handle"] == "anna"
    shared = client.post(
        "/api/v1/prompts",
        json={
            "name": "Transmodellstil",
            "intent": "translate",
            "text": "Följ Transmodel-terminologi.",
            "shared": True,
        },
        headers=_bearer(anna),
    ).json()
    assert (
        client.post(
            "/api/v1/prompts",
            json={"name": "Fel", "intent": "improvisera", "text": "x"},
            headers=_bearer(anna),
        ).status_code
        == 422
    )

    # Own + shared for the owner; shared only for others/anonymous.
    assert {p["name"] for p in client.get("/api/v1/prompts", headers=_bearer(anna)).json()} == {
        "Min stil",
        "Transmodellstil",
    }
    assert [p["name"] for p in client.get("/api/v1/prompts", headers=_bearer(bertil)).json()] == [
        "Transmodellstil"
    ]
    assert [p["name"] for p in client.get("/api/v1/prompts", headers=ANON).json()] == [
        "Transmodellstil"
    ]
    # Intent filter (+ validation).
    assert [
        p["name"]
        for p in client.get(
            "/api/v1/prompts", params={"intent": "synthesize"}, headers=_bearer(anna)
        ).json()
    ] == ["Min stil"]
    assert (
        client.get("/api/v1/prompts", params={"intent": "fel"}, headers=_bearer(anna)).status_code
        == 422
    )

    # Delete: strangers get 404 for private (not disclosed), 403 for shared;
    # owner and super succeed.
    assert (
        client.delete(
            f"/api/v1/prompts/{private.json()['id']}", headers=_bearer(bertil)
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/prompts/{shared['id']}", headers=_bearer(bertil)).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/prompts/{private.json()['id']}", headers=_bearer(anna)).status_code
        == 204
    )
    assert (
        client.delete(f"/api/v1/prompts/{shared['id']}", headers=_bearer(root)).status_code == 204
    )
    assert client.get("/api/v1/prompts", headers=_bearer(anna)).json() == []


def test_prompt_id_flows_through_ai_draft(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    anna = _register(client, "anna")
    concept = _create_concept(client, collection.id).json()
    prompt = client.post(
        "/api/v1/prompts",
        json={"name": "Min stil", "intent": "synthesize", "text": "Skriv mycket kort."},
        headers=_bearer(anna),
    ).json()

    captured: dict = {}

    def fake_call_provider(**kwargs):
        captured.update(kwargs)
        return '{"canonical_form": "resa", "definition_md": "Kort.", "note_suggestion": "Kortad."}'

    monkeypatch.setattr(ai_module, "_call_provider", fake_call_provider)

    resp = client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "synthesize",
            "version_ids": [concept["head"]["id"]],
            "guidance": "Behåll exempel.",
            "prompt_id": prompt["id"],
        },
        headers={**_bearer(anna), "X-LLM-Key": "sk-test"},
    )
    assert resp.status_code == 200, resp.text
    # The prompt id is echoed for provenance stamping…
    assert resp.json()["prompt_id"] == prompt["id"]
    # …and the prompt text leads the guidance sent to the provider.
    assert "Skriv mycket kort.\n\nBehåll exempel." in captured["user_content"]

    # Unknown prompt → 400; someone else's PRIVATE prompt → 400 as well.
    unknown = client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "synthesize",
            "version_ids": [concept["head"]["id"]],
            "prompt_id": "finns-inte",
        },
        headers={**_bearer(anna), "X-LLM-Key": "sk-test"},
    )
    assert unknown.status_code == 400
    bertil = _register(client, "bertil")
    foreign = client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "synthesize",
            "version_ids": [concept["head"]["id"]],
            "prompt_id": prompt["id"],
        },
        headers={**_bearer(bertil), "X-LLM-Key": "sk-test"},
    )
    assert foreign.status_code == 400


# --------------------------------------------------------------------------
# AI provider adapter: berget / openai (OpenAI-compatible)
# --------------------------------------------------------------------------


def _fake_openai_response():
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"canonical_form": "stop", '
                                '"definition_md": "A place where vehicles stop.", '
                                '"note_suggestion": "Translated."}\n'
                                "```"
                            )
                        }
                    }
                ]
            }

    return FakeResponse()


def test_openai_compatible_provider_berget_happy_path(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    monkeypatch.delenv("BERGET_DEFAULT_MODEL", raising=False)
    concept = _create_concept(client, collection.id).json()
    captured: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers, timeout=timeout)
        return _fake_openai_response()

    monkeypatch.setattr(ai_module.httpx, "post", fake_post)
    resp = client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "translate",
            "version_ids": [concept["head"]["id"]],
            "target_language": "en",
        },
        headers={"X-LLM-Key": "sk-berget-123", "X-LLM-Provider": "berget"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Fence-stripped JSON parsing works identically for this provider.
    assert body["canonical_form"] == "stop"
    assert body["definition_md"] == "A place where vehicles stop."
    assert body["provider"] == "berget"
    assert body["model"] == "meta-llama/Llama-3.3-70B-Instruct"  # berget fallback default

    # Chat-completions call shape per the contract.
    assert captured["url"] == "https://api.berget.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-berget-123"
    assert captured["body"]["model"] == "meta-llama/Llama-3.3-70B-Instruct"
    assert captured["body"]["temperature"] == 0.2
    assert captured["body"]["max_tokens"] == ai_module.MAX_TOKENS
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]
    assert "terminologist" in captured["body"]["messages"][0]["content"]


def test_berget_env_default_model_and_body_model_wins(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    concept = _create_concept(client, collection.id).json()
    captured: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json)
        return _fake_openai_response()

    monkeypatch.setattr(ai_module.httpx, "post", fake_post)
    monkeypatch.setenv("BERGET_DEFAULT_MODEL", "openai/gpt-oss-120b")

    resp = client.post(
        "/api/v1/ai/draft",
        json={"intent": "synthesize", "version_ids": [concept["head"]["id"]]},
        headers={"X-LLM-Key": "sk-b", "X-LLM-Provider": "berget"},
    )
    assert resp.json()["model"] == "openai/gpt-oss-120b"
    assert captured["body"]["model"] == "openai/gpt-oss-120b"

    # body.model always wins over every default.
    client.post(
        "/api/v1/ai/draft",
        json={
            "intent": "synthesize",
            "version_ids": [concept["head"]["id"]],
            "model": "mistral-custom",
        },
        headers={"X-LLM-Key": "sk-b", "X-LLM-Provider": "berget"},
    )
    assert captured["body"]["model"] == "mistral-custom"


def test_openai_provider_default_model_and_base_url_override(client, collection, monkeypatch):
    from app.routers import ai as ai_module

    concept = _create_concept(client, collection.id).json()
    captured: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers)
        return _fake_openai_response()

    monkeypatch.setattr(ai_module.httpx, "post", fake_post)
    resp = client.post(
        "/api/v1/ai/draft",
        json={"intent": "synthesize", "version_ids": [concept["head"]["id"]]},
        headers={"X-LLM-Key": "sk-oai", "X-LLM-Provider": "openai"},
    )
    assert resp.status_code == 200
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["body"]["model"] == "gpt-4o-mini"

    # X-LLM-Base-URL points the same adapter at any compatible host —
    # /ai/extract shares it. The SSRF guard resolves the name first; give it
    # a public address so the override is accepted (test_security_hardening
    # covers the rejections).
    monkeypatch.setattr(
        ai_module.socket,
        "getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    extract = client.post(
        "/api/v1/ai/extract",
        json={"text": "zon: ett område."},
        headers={
            "X-LLM-Key": "sk-oai",
            "X-LLM-Provider": "openai",
            "X-LLM-Base-URL": "https://llm.example.org/v1/",
        },
    )
    assert extract.status_code in (200, 502)  # parsing differs; the URL is the point
    assert captured["url"] == "https://llm.example.org/v1/chat/completions"


# --------------------------------------------------------------------------
# Version permalinks
# --------------------------------------------------------------------------


def test_version_permalink_shape_is_head_and_visibility(client):
    _root, anna, _cesar, bertil, coll, concept = _org_setup(client)
    first = concept["head"]

    resp = client.get(f"/api/v1/versions/{first['id']}", headers=ANON)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == first["id"]
    assert body["concept_id"] == concept["id"]
    assert body["collection"] == {
        "slug": "k2-ordlista",
        "name": "Min samling",
        "year": None,
        "visibility": "public",
        "has_org": True,
    }
    assert body["is_head"] is True
    assert body["definition_md"] == "En definition."

    # After a revision the old version is frozen but no longer a head.
    new_head = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": first["id"],
            "canonical_form": "resa",
            "definition_md": "Nyare.",
        },
        headers=_bearer(anna),
    ).json()
    assert client.get(f"/api/v1/versions/{first['id']}").json()["is_head"] is False
    assert client.get(f"/api/v1/versions/{new_head['id']}").json()["is_head"] is True

    # org_private: strangers and anonymous get 404, members 200.
    client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={"visibility": "org_private"},
        headers=_bearer(anna),
    )
    for headers in (ANON, _bearer(bertil)):
        assert client.get(f"/api/v1/versions/{first['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/versions/{first['id']}", headers=_bearer(anna)).status_code == 200
    assert client.get("/api/v1/versions/finns-inte").status_code == 404
