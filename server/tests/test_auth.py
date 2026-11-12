"""Night-2 tests: auth (register/login/me + claims), organisations with
membership guards, collection management authz and org_private visibility."""

from app.models import User
from tests.conftest import register_payload

ANON = {"X-User": ""}


def _register(client, handle, password="hemligt-losenord", display_name=None):
    """Email-first registration (iteration 4): the handle is auto-slugified from
    the display name — handle.title() slugifies back to the handle itself."""
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": f"{handle}@example.org",
                "display_name": display_name or handle.title(),
                "password": password,
            },
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


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


def test_register_login_me_roundtrip(client):
    auth = _register(client, "anna", display_name="Anna Andersson")
    assert auth["token"]
    # The handle is INTERNAL: auto-slugified from the display name (iteration 4).
    assert auth["user"]["handle"] == "anna-andersson"
    assert auth["user"]["display_name"] == "Anna Andersson"
    assert auth["user"]["email"] == "anna@example.org"
    assert auth["user"]["email_verified"] is False
    assert auth["user"]["memberships"] == []  # multi-org: a list, empty at birth

    # identifier matches EMAIL first (case-insensitively)…
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "Anna@Example.org", "password": "hemligt-losenord"},
    )
    assert login.status_code == 200
    # …then handle; the old {handle, password} body shape still works too.
    legacy = client.post(
        "/api/v1/auth/login",
        json={"handle": "Anna Andersson", "password": "hemligt-losenord"},
    )
    assert legacy.status_code == 200
    me = client.get("/api/v1/auth/me", headers=_bearer(login.json()))
    assert me.status_code == 200
    assert me.json()["id"] == auth["user"]["id"]
    assert me.json()["is_super_admin"] is True  # first registered user


def test_register_derives_handle_with_numeric_dedup(client):
    first = _register(client, "anna")
    second = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "anna.b@example.org",
                "display_name": "Anna",
                "password": "hemligt-losenord",
            },
        ),
    )
    assert second.status_code == 201
    assert first["user"]["handle"] == "anna"
    assert second.json()["user"]["handle"] == "anna-2"


def test_first_user_with_password_becomes_super_admin(client):
    first = _register(client, "forsta")
    second = _register(client, "andra")
    assert first["user"]["is_super_admin"] is True
    assert second["user"]["is_super_admin"] is False


def test_register_claims_unclaimed_author_and_keeps_display_name(client, db):
    """The /activate claim flow: an explicit handle + claim=True takes over an
    imported identity (password_hash IS NULL). Without the claim flag the same
    request gets a 409 pointer to the author page (tests/test_hardening.py)."""
    imported = User(handle="greta", display_name="Greta Garbo", affiliation="K2")
    db.add(imported)
    db.commit()

    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "greta@example.org",
                "handle": "greta",
                "claim": True,
                "display_name": "Något Annat",
                "password": "hemligt-losenord",
            },
        ),
    )
    assert resp.status_code == 201, resp.text
    auth = resp.json()
    assert auth["user"]["id"] == imported.id  # claimed, not duplicated
    assert auth["user"]["display_name"] == "Greta Garbo"  # kept
    assert auth["user"]["affiliation"] == "K2"

    login = client.post(
        "/api/v1/auth/login", json={"identifier": "greta", "password": "hemligt-losenord"}
    )
    assert login.status_code == 200


def test_register_taken_email_and_handle_conflict(client):
    _register(client, "anna")
    # Same email again → 409, regardless of display name.
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "anna@example.org",
                "display_name": "Anna 2",
                "password": "annat-losenord",
            },
        ),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_taken"
    # Claiming an already-passworded handle explicitly → 409 too.
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "annan@example.org",
                "handle": "anna",
                "display_name": "Kapare",
                "password": "annat-losenord",
            },
        ),
    )
    assert resp.status_code == 409
    # Garbage email → 422.
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{"email": "inte-en-adress", "display_name": "X Y", "password": "annat-losenord"},
        ),
    )
    assert resp.status_code == 422


def test_login_wrong_password_and_unknown_identifier_401(client):
    _register(client, "anna")
    wrong = client.post(
        "/api/v1/auth/login", json={"identifier": "anna@example.org", "password": "fel-losen"}
    )
    assert wrong.status_code == 401
    unknown = client.post("/api/v1/auth/login", json={"identifier": "okand", "password": "x"})
    assert unknown.status_code == 401
    # No identifier at all → 422.
    assert client.post("/api/v1/auth/login", json={"password": "x"}).status_code == 422


def test_me_requires_identity_and_survives_garbage_token(client):
    assert client.get("/api/v1/auth/me", headers=ANON).status_code == 401
    garbage = {"Authorization": "Bearer inte.en.jwt"}
    assert client.get("/api/v1/auth/me", headers=garbage).status_code == 401


# --------------------------------------------------------------------------
# Organisations
# --------------------------------------------------------------------------


def test_org_create_approve_flow_and_one_owned_org_per_user(client):
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")

    org = _create_org(client, anna)
    assert org["is_approved"] is False  # non-super creators await approval
    assert org["owner_user_id"] == anna["user"]["id"]  # creator becomes owner
    assert org["members"] == [
        {
            "user_id": anna["user"]["id"],
            "handle": "anna",
            "display_name": "Anna",
            "role": "admin",
            "kind": "member",
            "is_public": True,
        }
    ]

    # Creator (non-super) cannot approve; super admin can.
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(anna)).status_code == 403
    approved = client.post("/api/v1/orgs/k2/approve", headers=_bearer(super_admin))
    assert approved.status_code == 200
    assert approved.json()["is_approved"] is True

    # One OWNED org per user: anna cannot create (and thereby own) a second…
    resp = client.post(
        "/api/v1/orgs", json={"name": "Annat", "slug": "annat"}, headers=_bearer(anna)
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "already_owns_org"

    # …but CAN hold memberships in other orgs (multi-org 2026-07).
    _create_org(client, bertil, slug="bertils", name="Bertils organisation")
    added = client.post(
        "/api/v1/orgs/bertils/members",
        json={"handle": "anna", "role": "editor"},
        headers=_bearer(bertil),
    )
    assert added.status_code == 201
    me = client.get("/api/v1/auth/me", headers=_bearer(anna)).json()
    assert {(m["slug"], m["role"], m["is_owner"]) for m in me["memberships"]} == {
        ("k2", "admin", True),
        ("bertils", "editor", False),
    }

    # Super-admin-created orgs are auto-approved — with no owner and no
    # membership (G1: super admins never speak for an organisation).
    auto = _create_org(client, super_admin, slug="trafikverket", name="Trafikverket")
    assert auto["is_approved"] is True
    assert auto["owner_user_id"] is None
    assert auto["members"] == []


def test_org_member_add_role_and_remove_guards(client):
    _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    cesar = _register(client, "cesar")
    _create_org(client, anna)

    # Admin adds bertil as editor.
    added = client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "bertil", "role": "editor"},
        headers=_bearer(anna),
    )
    assert added.status_code == 201
    roles = {m["handle"]: m["role"] for m in added.json()["members"]}
    assert roles == {"anna": "admin", "bertil": "editor"}

    # Already a member of THIS org → 409; unknown handle → 404; bad role → 422.
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "bertil", "role": "viewer"},
            headers=_bearer(anna),
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "finns-inte", "role": "viewer"},
            headers=_bearer(anna),
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "cesar", "role": "chef"},
            headers=_bearer(anna),
        ).status_code
        == 422
    )
    # G1: super admins hold no memberships → 409; guests can never be admin → 422.
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "root", "role": "viewer"},
            headers=_bearer(anna),
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "cesar", "role": "admin", "kind": "guest"},
            headers=_bearer(anna),
        ).status_code
        == 422
    )

    # Multi-org (2026-07): owning/belonging to another org no longer blocks —
    # cesar owns his own org AND becomes a k2 member.
    _create_org(client, cesar, slug="cesars", name="Cesars organisation")
    other_org = client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "cesar", "role": "viewer"},
        headers=_bearer(anna),
    )
    assert other_org.status_code == 201
    roles = {m["handle"]: m["role"] for m in other_org.json()["members"]}
    assert roles == {"anna": "admin", "bertil": "editor", "cesar": "viewer"}

    # Non-admin member cannot manage members.
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "diana", "role": "viewer"},
            headers=_bearer(bertil),
        ).status_code
        == 403
    )

    # Role change + owner/last-admin protection.
    bertil_id = bertil["user"]["id"]
    anna_id = anna["user"]["id"]
    # guest+admin is invalid on PATCH too.
    assert (
        client.patch(
            f"/api/v1/orgs/k2/members/{bertil_id}",
            json={"role": "admin", "kind": "guest"},
            headers=_bearer(anna),
        ).status_code
        == 422
    )
    changed = client.patch(
        f"/api/v1/orgs/k2/members/{bertil_id}", json={"role": "viewer"}, headers=_bearer(anna)
    )
    assert changed.status_code == 200
    assert (
        client.patch(
            f"/api/v1/orgs/k2/members/{anna_id}", json={"role": "editor"}, headers=_bearer(anna)
        ).status_code
        == 409  # the owner must stay admin — and the org must keep an admin
    )
    assert (
        client.delete(f"/api/v1/orgs/k2/members/{anna_id}", headers=_bearer(anna)).status_code
        == 409  # the owner cannot be removed
    )
    assert (
        client.delete(f"/api/v1/orgs/k2/members/{bertil_id}", headers=_bearer(anna)).status_code
        == 204  # end-dated, never deleted (G2)
    )
    members = client.get("/api/v1/orgs/k2", headers=_bearer(anna)).json()["members"]
    assert [m["handle"] for m in members] == ["anna", "cesar"]


def test_org_listing_scoped_and_hidden_from_outsiders(client):
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    _create_org(client, anna)

    assert [o["slug"] for o in client.get("/api/v1/orgs", headers=_bearer(anna)).json()] == ["k2"]
    assert client.get("/api/v1/orgs", headers=_bearer(bertil)).json() == []
    assert len(client.get("/api/v1/orgs", headers=_bearer(super_admin)).json()) == 1
    # Direct fetch hidden from non-members (404, not 403).
    assert client.get("/api/v1/orgs/k2", headers=_bearer(bertil)).status_code == 404
    assert client.get("/api/v1/orgs", headers=ANON).status_code == 401


# --------------------------------------------------------------------------
# Collections: management authz
# --------------------------------------------------------------------------


def test_create_collection_requires_auth_validates_slug_and_conflicts(client):
    anna = _register(client, "anna")
    anon = client.post("/api/v1/collections", json={"slug": "x-y", "name": "X"}, headers=ANON)
    assert anon.status_code == 401
    bad_slug = client.post(
        "/api/v1/collections", json={"slug": "Å Ä Ö", "name": "X"}, headers=_bearer(anna)
    )
    assert bad_slug.status_code == 422

    # anna is the FIRST registered user → super admin, so an org-less PUBLIC
    # (system) collection is allowed and manageable for her (funnel, beslut 2).
    created = _create_collection(client, anna, slug="ordlista", year=2026)
    assert created["created_by"] == "anna"
    assert created["visibility"] == "public"
    assert created["editable"] is True

    dup = client.post(
        "/api/v1/collections", json={"slug": "ordlista", "name": "Kopia"}, headers=_bearer(anna)
    )
    assert dup.status_code == 409


def test_patch_collection_member_vs_stranger_vs_super(client):
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    cesar = _register(client, "cesar")
    org = _create_org(client, anna)
    # Org-owned collections require an APPROVED organisation (2026-07).
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(super_admin)).status_code == 200
    client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "cesar", "role": "editor"},
        headers=_bearer(anna),
    )
    coll = _create_collection(client, anna, slug="k2-ordlista", organisation_id=org["id"])
    assert coll["organisation"]["slug"] == "k2"

    # Stranger: can see it (public) but not manage it.
    stranger = client.patch(
        "/api/v1/collections/k2-ordlista", json={"name": "Kapad"}, headers=_bearer(bertil)
    )
    assert stranger.status_code == 403
    # Editor member: concept writes yes, metadata no (org admin only).
    assert (
        client.patch(
            "/api/v1/collections/k2-ordlista", json={"name": "Nytt"}, headers=_bearer(cesar)
        ).status_code
        == 403
    )
    # Org admin: yes.
    patched = client.patch(
        "/api/v1/collections/k2-ordlista",
        json={"name": "K2:s ordlista", "licence": {"label": "CC BY 4.0"}},
        headers=_bearer(anna),
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "K2:s ordlista"
    assert patched.json()["licence"] == {"label": "CC BY 4.0"}

    # authoritative: super admin only.
    assert (
        client.patch(
            "/api/v1/collections/k2-ordlista",
            json={"authoritative": True},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    superset = client.patch(
        "/api/v1/collections/k2-ordlista",
        json={"authoritative": True},
        headers=_bearer(super_admin),
    )
    assert superset.status_code == 200
    assert superset.json()["authoritative"] is True


# --------------------------------------------------------------------------
# Visibility: org_private hiding
# --------------------------------------------------------------------------


def _private_setup(client):
    """root (super), anna (org admin), bertil (stranger) + an org_private collection."""
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    org = _create_org(client, anna)
    # Org-owned collections require an APPROVED organisation (2026-07).
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(super_admin)).status_code == 200
    coll = _create_collection(
        client, anna, slug="internt", organisation_id=org["id"], visibility="org_private"
    )
    concept = _create_concept(client, coll["id"], form="internbegrepp", headers=_bearer(anna))
    assert concept.status_code == 201
    return super_admin, anna, bertil, coll, concept.json()


def test_org_private_collection_hidden_from_anonymous_and_strangers(client):
    super_admin, anna, bertil, coll, concept = _private_setup(client)

    for headers in (ANON, _bearer(bertil)):
        listed = [c["slug"] for c in client.get("/api/v1/collections", headers=headers).json()]
        assert "internt" not in listed
        assert client.get("/api/v1/collections/internt", headers=headers).status_code == 404
        assert client.get(f"/api/v1/concepts/{concept['id']}", headers=headers).status_code == 404
        assert (
            client.get(f"/api/v1/concepts/{concept['id']}/graph", headers=headers).status_code
            == 404
        )
        search = client.get("/api/v1/concepts", params={"q": "internbegrepp"}, headers=headers)
        assert search.json()["total"] == 0
        assert (
            client.get(
                "/api/v1/collections/internt/export",
                params={"format": "csv"},
                headers=headers,
            ).status_code
            == 404
        )

    # Member and super admin see everything.
    for headers in (_bearer(anna), _bearer(super_admin)):
        assert client.get("/api/v1/collections/internt", headers=headers).status_code == 200
        assert client.get(f"/api/v1/concepts/{concept['id']}", headers=headers).status_code == 200
    member_view = client.get("/api/v1/collections/internt", headers=_bearer(anna)).json()
    assert member_view["visibility"] == "org_private"
    assert member_view["editable"] is True


def test_concept_writes_in_org_collection_require_membership(client):
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    bertil = _register(client, "bertil")
    diana = _register(client, "diana")
    org = _create_org(client, anna)
    # Org-owned collections require an APPROVED organisation (2026-07).
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(super_admin)).status_code == 200
    client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "diana", "role": "viewer"},
        headers=_bearer(anna),
    )
    coll = _create_collection(client, anna, slug="k2-publik", organisation_id=org["id"])

    # Stranger and viewer get a structured 403; anonymous 401.
    stranger = _create_concept(client, coll["id"], headers=_bearer(bertil))
    assert stranger.status_code == 403
    assert stranger.json()["detail"]["code"] == "collection_edit_forbidden"
    assert _create_concept(client, coll["id"], headers=_bearer(diana)).status_code == 403
    assert _create_concept(client, coll["id"], headers=ANON).status_code == 401

    # Org admin writes; version writes follow the same rule.
    created = _create_concept(client, coll["id"], headers=_bearer(anna))
    assert created.status_code == 201
    concept = created.json()
    revise = {
        "mode": "revise",
        "base_version_id": concept["head"]["id"],
        "canonical_form": "hållplats",
        "definition_md": "Ny text.",
    }
    denied = client.post(
        f"/api/v1/concepts/{concept['id']}/versions", json=revise, headers=_bearer(bertil)
    )
    assert denied.status_code == 403
    allowed = client.post(
        f"/api/v1/concepts/{concept['id']}/versions", json=revise, headers=_bearer(anna)
    )
    assert allowed.status_code == 201


def test_orgless_public_collection_accepts_any_signed_user(client, collection):
    # Dev parity: X-User signature is enough in org-less public collections.
    assert _create_concept(client, collection.id).status_code == 201  # default X-User
    assert _create_concept(client, collection.id, form="tur", headers=ANON).status_code == 401


# --------------------------------------------------------------------------
# Concepts: status filter
# --------------------------------------------------------------------------


def test_status_filter_on_concepts_list(client, collection):
    _create_concept(client, collection.id, form="utkastet", status="draft")
    _create_concept(client, collection.id, form="forslaget", status="proposed")
    _create_concept(client, collection.id, form="utfasat", status="deprecated")

    only_draft = client.get("/api/v1/concepts", params={"status": "draft"}).json()
    assert [i["canonical_form"] for i in only_draft["items"]] == ["utkastet"]

    combo = client.get("/api/v1/concepts", params={"status": "draft,deprecated"}).json()
    assert sorted(i["canonical_form"] for i in combo["items"]) == ["utfasat", "utkastet"]
    assert combo["total"] == 2
