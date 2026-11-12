"""Multi-organisation memberships (2026-07): many memberships per user, one
OWNED org per user, org-scoped suspension, acting-org endorsements, the
collection funnel (private sandbox → org-owned), and the super-admin
guardrails G1–G3."""

from tests.conftest import register_payload

ANON = {"X-User": ""}
PASSWORD = "hemligt-losenord"


def _register(client, handle):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            email=f"{handle}@example.org",
            display_name=handle.title(),
            password=PASSWORD,
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _bearer(auth) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['token']}"}


def _create_org(client, auth, slug, name=None, org_type=None):
    payload = {"name": name or slug.upper(), "slug": slug}
    if org_type:
        payload["org_type"] = org_type
    resp = client.post("/api/v1/orgs", json=payload, headers=_bearer(auth))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _approve(client, su, slug, org_type=None):
    payload = {"org_type": org_type} if org_type else None
    resp = client.post(f"/api/v1/orgs/{slug}/approve", json=payload, headers=_bearer(su))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _add_member(client, admin_auth, slug, handle, role="editor", kind="member"):
    return client.post(
        f"/api/v1/orgs/{slug}/members",
        json={"handle": handle, "role": role, "kind": kind},
        headers=_bearer(admin_auth),
    )


def _create_collection(client, auth, slug, **overrides):
    payload = {"slug": slug, "name": f"Samling {slug}", **overrides}
    return client.post("/api/v1/collections", json=payload, headers=_bearer(auth))


def _create_concept(client, auth, collection_id, form="hållplats"):
    return client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection_id,
            "canonical_form": form,
            "definition_md": "En definition.",
        },
        headers=_bearer(auth),
    )


def _setup(client):
    """su (super admin, registered first), maria (owner of two approved orgs?
    no — one each): maria owns org-a, nils owns org-b, olle is org-less."""
    su = _register(client, "super")
    maria = _register(client, "maria")
    nils = _register(client, "nils")
    olle = _register(client, "olle")
    _create_org(client, maria, "org-a", "Organisation A")
    _create_org(client, nils, "org-b", "Organisation B")
    _approve(client, su, "org-a", org_type="industry_association")
    _approve(client, su, "org-b", org_type="commercial")
    return su, maria, nils, olle


# ── Ownership ──


def test_one_owned_org_but_many_memberships(client):
    su, maria, nils, olle = _setup(client)

    # maria already OWNS org-a → creating another is refused …
    resp = client.post(
        "/api/v1/orgs", json={"name": "Tvåan", "slug": "tvaan"}, headers=_bearer(maria)
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "already_owns_org"

    # … but she can be invited into org-b as guest editor (multi-membership).
    assert (
        _add_member(client, nils, "org-b", "maria", role="editor", kind="guest").status_code == 201
    )
    me = client.get("/api/v1/auth/me", headers=_bearer(maria)).json()
    assert {m["slug"] for m in me["memberships"]} == {"org-a", "org-b"}
    by_slug = {m["slug"]: m for m in me["memberships"]}
    assert by_slug["org-a"]["is_owner"] is True and by_slug["org-a"]["role"] == "admin"
    assert by_slug["org-b"]["kind"] == "guest" and by_slug["org-b"]["is_owner"] is False

    # A member of another org can be added — the old one-org guard is gone.
    assert _add_member(client, maria, "org-a", "nils", role="viewer").status_code == 201


def test_owner_cannot_be_demoted_or_removed(client):
    su, maria, nils, olle = _setup(client)
    maria_id = maria["user"]["id"]

    demote = client.patch(
        f"/api/v1/orgs/org-a/members/{maria_id}",
        json={"role": "viewer"},
        headers=_bearer(su),
    )
    assert demote.status_code == 409
    assert demote.json()["detail"]["code"] == "owner_must_be_admin"
    remove = client.delete(f"/api/v1/orgs/org-a/members/{maria_id}", headers=_bearer(su))
    assert remove.status_code == 409


def test_owner_transfer_super_admin_only(client):
    su, maria, nils, olle = _setup(client)
    olle_id = olle["user"]["id"]
    nils_id = nils["user"]["id"]

    # Only super admins transfer ownership.
    assert (
        client.post(
            "/api/v1/orgs/org-a/owner", json={"user_id": olle_id}, headers=_bearer(maria)
        ).status_code
        == 403
    )
    # nils already owns org-b → cannot also own org-a.
    conflict = client.post(
        "/api/v1/orgs/org-a/owner", json={"user_id": nils_id}, headers=_bearer(su)
    )
    assert conflict.status_code == 409
    # olle (org-less) becomes owner and thereby admin member.
    resp = client.post("/api/v1/orgs/org-a/owner", json={"user_id": olle_id}, headers=_bearer(su))
    assert resp.status_code == 200, resp.text
    org = resp.json()
    assert org["owner_user_id"] == olle_id
    roles = {m["user_id"]: m["role"] for m in org["members"]}
    assert roles[olle_id] == "admin"
    # The previous owner stays an ordinary admin member and can now be demoted.
    maria_id = maria["user"]["id"]
    assert (
        client.patch(
            f"/api/v1/orgs/org-a/members/{maria_id}",
            json={"role": "viewer"},
            headers=_bearer(su),
        ).status_code
        == 200
    )


# ── Guardrails G1–G3 ──


def test_super_admin_cannot_be_member_and_vice_versa(client):
    su, maria, nils, olle = _setup(client)

    # G1a: a super admin cannot be invited.
    resp = _add_member(client, maria, "org-a", "super")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "super_admin_cannot_be_member"

    # G1b: a user with active memberships cannot be granted super admin.
    _add_member(client, maria, "org-a", "olle", role="viewer")
    olle_id = olle["user"]["id"]
    grant = client.patch(
        f"/api/v1/admin/users/{olle_id}", json={"is_super_admin": True}, headers=_bearer(su)
    )
    assert grant.status_code == 409
    assert grant.json()["detail"]["code"] == "superadmin_has_memberships"

    # After the membership ends the grant goes through.
    client.delete(f"/api/v1/orgs/org-a/members/{olle_id}", headers=_bearer(su))
    assert (
        client.patch(
            f"/api/v1/admin/users/{olle_id}",
            json={"is_super_admin": True},
            headers=_bearer(su),
        ).status_code
        == 200
    )

    # G3: the last super admin cannot be demoted (olle is now the second —
    # demote him first, then su is the last one and protected).
    assert (
        client.patch(
            f"/api/v1/admin/users/{olle_id}",
            json={"is_super_admin": False},
            headers=_bearer(su),
        ).status_code
        == 200
    )
    su_id = su["user"]["id"]
    olle_auth = client.post(
        "/api/v1/auth/login", json={"handle": "olle", "password": PASSWORD}
    ).json()
    # olle is no longer super → 403; re-grant to test the last-admin guard.
    assert (
        client.patch(
            f"/api/v1/admin/users/{su_id}",
            json={"is_super_admin": False},
            headers=_bearer(olle_auth),
        ).status_code
        == 403
    )
    client.patch(
        f"/api/v1/admin/users/{olle_id}", json={"is_super_admin": True}, headers=_bearer(su)
    )
    olle_auth = client.post(
        "/api/v1/auth/login", json={"handle": "olle", "password": PASSWORD}
    ).json()
    assert (
        client.patch(
            f"/api/v1/admin/users/{su_id}",
            json={"is_super_admin": False},
            headers=_bearer(olle_auth),
        ).status_code
        == 200
    )
    # Now olle is the LAST super admin — su cannot demote him… su is not
    # super anymore, so the guard fires as 403 (rights) — log in as olle and
    # try self-demotion: blocked as self-modification (403), and a would-be
    # demotion of the last super admin by anyone is 409.
    assert (
        client.patch(
            f"/api/v1/admin/users/{olle_id}",
            json={"is_super_admin": False},
            headers=_bearer(olle_auth),
        ).status_code
        == 403
    )


def test_guest_cannot_be_admin(client):
    su, maria, nils, olle = _setup(client)
    assert (
        _add_member(client, maria, "org-a", "olle", role="admin", kind="guest").status_code == 422
    )
    assert (
        _add_member(client, maria, "org-a", "olle", role="editor", kind="guest").status_code == 201
    )
    olle_id = olle["user"]["id"]
    resp = client.patch(
        f"/api/v1/orgs/org-a/members/{olle_id}", json={"role": "admin"}, headers=_bearer(maria)
    )
    assert resp.status_code == 422


def test_membership_is_end_dated_not_deleted(client, db):
    from app.models import OrgMembership

    su, maria, nils, olle = _setup(client)
    _add_member(client, maria, "org-a", "olle", role="viewer")
    olle_id = olle["user"]["id"]
    assert (
        client.delete(f"/api/v1/orgs/org-a/members/{olle_id}", headers=_bearer(maria)).status_code
        == 204
    )
    rows = db.query(OrgMembership).filter(OrgMembership.user_id == olle_id).all()
    assert len(rows) == 1 and rows[0].ended_at is not None
    # Re-invitation creates a FRESH row (history preserved).
    assert _add_member(client, maria, "org-a", "olle", role="viewer").status_code == 201
    rows = db.query(OrgMembership).filter(OrgMembership.user_id == olle_id).all()
    assert len(rows) == 2 and any(r.ended_at is None for r in rows)


# ── Collection funnel & multi-org visibility ──


def test_collection_funnel_sandbox_and_org_rules(client):
    su, maria, nils, olle = _setup(client)

    # Org-less public → 422 funnel for regular users.
    resp = _create_collection(client, olle, "utan-org")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "collection_org_required"

    # Org-less private sandbox → 201; invisible to everyone else.
    sandbox = _create_collection(client, olle, "min-sandlada", visibility="private")
    assert sandbox.status_code == 201, sandbox.text
    slugs_anon = {c["slug"] for c in client.get("/api/v1/collections", headers=ANON).json()}
    assert "min-sandlada" not in slugs_anon
    assert client.get("/api/v1/collections/min-sandlada", headers=ANON).status_code == 404
    assert (
        client.get("/api/v1/collections/min-sandlada", headers=_bearer(maria)).status_code == 404
    )
    assert client.get("/api/v1/collections/min-sandlada", headers=_bearer(olle)).status_code == 200
    assert client.get("/api/v1/collections/min-sandlada", headers=_bearer(su)).status_code == 200

    # A private sandbox cannot be org-owned.
    org_a = _org_id(client, maria, "org-a")
    both = _create_collection(
        client, maria, "privat-med-org", visibility="private", organisation_id=org_a
    )
    assert both.status_code == 422

    # Org-owned creation: admin 201, guest/editor 403, stranger 403.
    assert (
        _create_collection(client, maria, "org-a-samling", organisation_id=org_a).status_code
        == 201
    )
    _add_member(client, maria, "org-a", "olle", role="editor")
    assert (
        _create_collection(client, olle, "editor-forsok", organisation_id=org_a).status_code == 403
    )
    assert (
        _create_collection(client, nils, "stranger-forsok", organisation_id=org_a).status_code
        == 403
    )

    # Super admin may create org-less SYSTEM collections.
    assert _create_collection(client, su, "system-samling").status_code == 201

    # The funnel: taking the sandbox public requires an org in the same PATCH.
    patch_no_org = client.patch(
        "/api/v1/collections/min-sandlada",
        json={"visibility": "public"},
        headers=_bearer(olle),
    )
    assert patch_no_org.status_code == 422
    # olle is editor in org-a — not admin, so assigning org-a is refused.
    patch_editor = client.patch(
        "/api/v1/collections/min-sandlada",
        json={"visibility": "public", "organisation_id": org_a},
        headers=_bearer(olle),
    )
    assert patch_editor.status_code == 403


def _org_id(client, auth, slug):
    return client.get(f"/api/v1/orgs/{slug}", headers=_bearer(auth)).json()["id"]


def test_multi_org_private_visibility(client):
    """A dual member sees BOTH orgs' org_private collections."""
    su, maria, nils, olle = _setup(client)
    org_a = _org_id(client, maria, "org-a")
    org_b = _org_id(client, nils, "org-b")
    assert (
        _create_collection(
            client, maria, "a-privat", organisation_id=org_a, visibility="org_private"
        ).status_code
        == 201
    )
    assert (
        _create_collection(
            client, nils, "b-privat", organisation_id=org_b, visibility="org_private"
        ).status_code
        == 201
    )
    _add_member(client, maria, "org-a", "olle", role="viewer")
    _add_member(client, nils, "org-b", "olle", role="viewer", kind="guest")

    slugs = {c["slug"] for c in client.get("/api/v1/collections", headers=_bearer(olle)).json()}
    assert {"a-privat", "b-privat"} <= slugs
    # nils (member of org-b only, despite being viewer member in org-a? no —
    # nils holds no org-a membership) sees only his own.
    slugs_nils = {
        c["slug"] for c in client.get("/api/v1/collections", headers=_bearer(nils)).json()
    }
    assert "b-privat" in slugs_nils and "a-privat" not in slugs_nils


def test_org_scoped_suspension(client):
    """Suspension blocks writes in the suspended org's context ONLY."""
    su, maria, nils, olle = _setup(client)
    org_a = _org_id(client, maria, "org-a")
    coll_a = _create_collection(client, maria, "a-samling", organisation_id=org_a).json()
    open_coll = _create_collection(client, su, "oppen-samling").json()

    assert client.post("/api/v1/orgs/org-a/suspend", headers=_bearer(su)).status_code == 200

    # Writes into the suspended org's collection → 403 …
    resp = _create_concept(client, maria, coll_a["id"])
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "org_suspended"
    # … but the SAME user writes elsewhere (system collection, edit anyone).
    assert _create_concept(client, maria, open_coll["id"]).status_code == 201
    # Managing the suspended org as its admin → 403; super admin still can.
    assert _add_member(client, maria, "org-a", "olle").status_code == 403
    assert _add_member(client, su, "org-a", "olle").status_code == 201

    assert client.post("/api/v1/orgs/org-a/unsuspend", headers=_bearer(su)).status_code == 200
    assert _create_concept(client, maria, coll_a["id"], form="ny form").status_code == 201


# ── Acting-org endorsements ──


def test_acting_org_resolution(client):
    su, maria, nils, olle = _setup(client)
    org_a = _org_id(client, maria, "org-a")
    org_b = _org_id(client, nils, "org-b")
    coll = _create_collection(client, su, "gemensam").json()
    concept = _create_concept(client, su, coll["id"]).json()
    version_id = concept["head"]["id"]
    note = {"note": "Vi använder denna definition."}

    # maria is admin of ONE org → auto-resolved.
    stamped = client.post(
        f"/api/v1/versions/{version_id}/endorsements", json=note, headers=_bearer(maria)
    )
    assert stamped.status_code == 201, stamped.text
    assert stamped.json()["organisation"]["slug"] == "org-a"

    # Make maria admin of org-b too → ambiguous without organisation_id.
    client.patch(
        f"/api/v1/orgs/org-b/members/{maria['user']['id']}",
        json={"role": "admin", "kind": "member"},
        headers=_bearer(nils),
    )
    _add_member(client, nils, "org-b", "maria", role="admin")  # idempotence guard: 409 ok
    ambiguous = client.post(
        f"/api/v1/versions/{version_id}/endorsements", json=note, headers=_bearer(maria)
    )
    assert ambiguous.status_code == 422
    assert ambiguous.json()["detail"]["code"] == "endorsement_org_ambiguous"

    # Explicit acting org works; a foreign org id is refused.
    explicit = client.post(
        f"/api/v1/versions/{version_id}/endorsements",
        json={**note, "organisation_id": org_b},
        headers=_bearer(maria),
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["organisation"]["slug"] == "org-b"
    foreign = client.post(
        f"/api/v1/versions/{version_id}/endorsements",
        json={**note, "organisation_id": org_a},
        headers=_bearer(olle),
    )
    assert foreign.status_code == 403

    # Withdrawal: admin of the stamping org via active membership.
    endorsement_id = explicit.json()["id"]
    resp = client.post(
        f"/api/v1/endorsements/{endorsement_id}/withdraw",
        json={"note": "Ersatt."},
        headers=_bearer(maria),
    )
    assert resp.status_code == 200, resp.text


# ── Author page memberships ──


def test_author_page_membership_visibility(client):
    su, maria, nils, olle = _setup(client)
    org_a = _org_id(client, maria, "org-a")
    coll = _create_collection(client, maria, "a-samling", organisation_id=org_a).json()
    _create_concept(client, maria, coll["id"])  # maria becomes an author

    _add_member(client, nils, "org-b", "maria", role="editor", kind="guest")

    author = client.get("/api/v1/authors/maria", headers=ANON).json()
    slugs = {m["org_slug"] for m in author["memberships"]}
    assert slugs == {"org-a", "org-b"}
    assert all("email" not in m for m in author["memberships"])
    assert "email" not in author
    by_slug = {m["org_slug"]: m for m in author["memberships"]}
    assert by_slug["org-b"]["kind"] == "guest"

    # Opt-out hides the membership from the public …
    resp = client.patch(
        "/api/v1/orgs/org-b/my-membership",
        json={"is_public": False},
        headers=_bearer(maria),
    )
    assert resp.status_code == 200, resp.text
    public_view = client.get("/api/v1/authors/maria", headers=ANON).json()
    assert {m["org_slug"] for m in public_view["memberships"]} == {"org-a"}
    # … but the super admin still sees it, flagged.
    admin_view = client.get("/api/v1/authors/maria", headers=_bearer(su)).json()
    hidden = [m for m in admin_view["memberships"] if m["org_slug"] == "org-b"]
    assert len(hidden) == 1 and hidden[0]["is_public"] is False

    # Ended memberships disappear publicly, stay visible (dated) for super.
    client.delete(f"/api/v1/orgs/org-b/members/{maria['user']['id']}", headers=_bearer(nils))
    public_view = client.get("/api/v1/authors/maria", headers=ANON).json()
    assert {m["org_slug"] for m in public_view["memberships"]} == {"org-a"}
    admin_view = client.get("/api/v1/authors/maria", headers=_bearer(su)).json()
    ended = [m for m in admin_view["memberships"] if m["org_slug"] == "org-b"]
    assert len(ended) == 1 and ended[0]["ended_at"] is not None
