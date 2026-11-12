"""Night-3 tests: auth hardening (refresh rotation, logout, password change,
reset links, is_active, rate limiting, DEV_AUTH gating), stats visibility,
endorsements, collection lock/archive 423 semantics, org suspension and the
admin users surface."""

from datetime import UTC, datetime, timedelta

from app import ratelimit
from app.models import RefreshToken, ResetToken
from tests.conftest import register_payload

ANON = {"X-User": ""}
REFRESH_COOKIE = "kollepedia_refresh"
PASSWORD = "hemligt-losenord"


def _register(client, handle, password=PASSWORD, display_name=None):
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


def _login(client, handle, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"handle": handle, "password": password})


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


def _cookie_refresh(client, raw):
    """POST /auth/refresh presenting an explicit cookie value (bypasses the jar)."""
    return client.post("/api/v1/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={raw}"})


def _org_locked_setup(client):
    """root (super), anna (admin of the APPROVED org k2), cesar (editor
    member), bertil (org-less stranger) + a PUBLIC org-owned collection with
    two concepts and one relation. Approval is needed up front: org-owned
    collections can only be created under an approved organisation."""
    root = _register(client, "root")
    anna = _register(client, "anna")
    cesar = _register(client, "cesar")
    bertil = _register(client, "bertil")
    org = _create_org(client, anna)
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(root)).status_code == 200
    client.post(
        "/api/v1/orgs/k2/members",
        json={"handle": "cesar", "role": "editor"},
        headers=_bearer(anna),
    )
    coll = _create_collection(client, anna, slug="k2-ordlista", organisation_id=org["id"])
    a = _create_concept(client, coll["id"], form="resa", headers=_bearer(anna)).json()
    b = _create_concept(client, coll["id"], form="tur", headers=_bearer(anna)).json()
    rel = client.post(
        "/api/v1/relations",
        json={"relation_type": "related_to", "from_concept_id": a["id"], "to_concept_id": b["id"]},
        headers=_bearer(anna),
    )
    assert rel.status_code == 201
    return root, anna, cesar, bertil, coll, a, b, rel.json()["id"]


# --------------------------------------------------------------------------
# Refresh tokens: cookie, rotation, replay, logout
# --------------------------------------------------------------------------


def test_login_and_register_set_httponly_refresh_cookie(client):
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client, **{"email": "anna@example.org", "display_name": "Anna", "password": PASSWORD}
        ),
    )
    assert resp.status_code == 201
    set_cookie = resp.headers.get("set-cookie", "")
    assert REFRESH_COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie.replace("samesite", "SameSite")

    login = _login(client, "anna")
    assert login.status_code == 200
    assert REFRESH_COOKIE in login.headers.get("set-cookie", "")


def test_refresh_rotates_and_rejects_replayed_token(client):
    auth = _register(client, "anna")
    first = client.cookies.get(REFRESH_COOKIE)
    assert first

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["token"]
    assert rotated.json()["user"]["id"] == auth["user"]["id"]
    second = client.cookies.get(REFRESH_COOKIE)
    assert second and second != first

    # Replaying the revoked first token is a hard 401; the rotated one works.
    assert _cookie_refresh(client, first).status_code == 401
    assert _cookie_refresh(client, second).status_code == 200

    # No cookie at all → 401; garbage cookie → 401.
    client.cookies.clear()
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert _cookie_refresh(client, "inte-en-token").status_code == 401


def test_refresh_rejects_expired_token(client, db):
    _register(client, "anna")
    raw = client.cookies.get(REFRESH_COOKIE)
    db.query(RefreshToken).update({RefreshToken.expires_at: datetime.now(UTC) - timedelta(days=1)})
    db.commit()
    assert _cookie_refresh(client, raw).status_code == 401


def test_logout_revokes_refresh_token_and_clears_cookie(client):
    _register(client, "anna")
    raw = client.cookies.get(REFRESH_COOKIE)
    assert client.post("/api/v1/auth/logout").status_code == 204
    # The revoked token is dead even when presented explicitly.
    assert _cookie_refresh(client, raw).status_code == 401
    # And the jar cookie was cleared → nothing to send.
    assert client.post("/api/v1/auth/refresh").status_code == 401


# --------------------------------------------------------------------------
# Password change + reset links
# --------------------------------------------------------------------------


def test_password_change_requires_correct_current(client):
    auth = _register(client, "anna")
    wrong = client.post(
        "/api/v1/auth/password",
        json={"current_password": "fel-losen", "new_password": "nytt-losenord"},
        headers=_bearer(auth),
    )
    assert wrong.status_code == 403
    ok = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "nytt-losenord"},
        headers=_bearer(auth),
    )
    assert ok.status_code == 204
    assert _login(client, "anna").status_code == 401  # old password dead
    assert _login(client, "anna", "nytt-losenord").status_code == 200

    # A bare dev signature has no password to change.
    no_pw = client.post(
        "/api/v1/auth/password",
        json={"current_password": "x", "new_password": "nytt-losenord"},
    )
    assert no_pw.status_code == 403
    # Anonymous → 401.
    assert (
        client.post(
            "/api/v1/auth/password",
            json={"current_password": "x", "new_password": "nytt-losenord"},
            headers=ANON,
        ).status_code
        == 401
    )


def test_reset_link_flow_one_time_and_revokes_sessions(client):
    root = _register(client, "root")
    anna = _register(client, "anna")
    anna_refresh = client.cookies.get(REFRESH_COOKIE)  # anna registered last

    # Only super admins mint reset links.
    forbidden = client.post(
        f"/api/v1/admin/users/{anna['user']['id']}/reset-link", headers=_bearer(anna)
    )
    assert forbidden.status_code == 403
    missing = client.post("/api/v1/admin/users/finns-inte/reset-link", headers=_bearer(root))
    assert missing.status_code == 404

    minted = client.post(
        f"/api/v1/admin/users/{anna['user']['id']}/reset-link", headers=_bearer(root)
    )
    assert minted.status_code == 201, minted.text
    assert minted.json()["url"].startswith("/reset?token=")
    assert minted.json()["expires_at"]
    token = minted.json()["url"].split("token=", 1)[1]

    reset = client.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "splitternytt-1"}
    )
    assert reset.status_code == 204
    assert _login(client, "anna", PASSWORD).status_code == 401
    assert _login(client, "anna", "splitternytt-1").status_code == 200
    # One-time: the consumed token is dead.
    assert (
        client.post(
            "/api/v1/auth/reset", json={"token": token, "new_password": "annat-nytt-1"}
        ).status_code
        == 400
    )
    # All of anna's pre-reset refresh tokens were revoked.
    assert _cookie_refresh(client, anna_refresh).status_code == 401
    # Garbage token → 400.
    assert (
        client.post(
            "/api/v1/auth/reset", json={"token": "paahittad", "new_password": "nytt-losen-1"}
        ).status_code
        == 400
    )


def test_reset_link_expires_after_24h(client, db):
    root = _register(client, "root")
    anna = _register(client, "anna")
    minted = client.post(
        f"/api/v1/admin/users/{anna['user']['id']}/reset-link", headers=_bearer(root)
    )
    token = minted.json()["url"].split("token=", 1)[1]
    db.query(ResetToken).update({ResetToken.expires_at: datetime.now(UTC) - timedelta(minutes=1)})
    db.commit()
    resp = client.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "nytt-losenord-1"}
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# is_active
# --------------------------------------------------------------------------


def test_inactive_user_blocked_from_login_refresh_and_writes(client, collection):
    root = _register(client, "root")
    anna = _register(client, "anna")
    anna_refresh = client.cookies.get(REFRESH_COOKIE)

    deactivated = client.patch(
        f"/api/v1/admin/users/{anna['user']['id']}",
        json={"is_active": False},
        headers=_bearer(root),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    assert _login(client, "anna").status_code == 403
    assert _cookie_refresh(client, anna_refresh).status_code in (401, 403)
    # Existing bearer token no longer writes (or even identifies).
    assert _create_concept(client, collection.id, headers=_bearer(anna)).status_code == 403
    assert client.get("/api/v1/auth/me", headers=_bearer(anna)).status_code == 403

    # Reactivation restores everything.
    client.patch(
        f"/api/v1/admin/users/{anna['user']['id']}",
        json={"is_active": True},
        headers=_bearer(root),
    )
    assert _login(client, "anna").status_code == 200
    assert _create_concept(client, collection.id, headers=_bearer(anna)).status_code == 201


# --------------------------------------------------------------------------
# Rate limiting + DEV_AUTH gating
# --------------------------------------------------------------------------


def test_auth_rate_limit_429_with_retry_after(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH", "3")
    ratelimit.reset()
    for _ in range(3):
        resp = _login(client, "okand", "fel")
        assert resp.status_code == 401  # counted, but under the limit
    blocked = _login(client, "okand", "fel")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # Other route classes are unaffected.
    assert client.get("/api/v1/collections").status_code == 200
    # A fresh window (reset hook) lets traffic through again.
    ratelimit.reset()
    assert _login(client, "okand", "fel").status_code == 401


def test_dev_auth_disabled_rejects_x_user_but_keeps_bearer(client, collection, monkeypatch):
    auth = _register(client, "anna")
    monkeypatch.setenv("DEV_AUTH", "0")
    # The client's default X-User signature is no longer honoured.
    assert _create_concept(client, collection.id).status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    # Real tokens still work.
    assert _create_concept(client, collection.id, headers=_bearer(auth)).status_code == 201
    monkeypatch.setenv("DEV_AUTH", "1")
    assert _create_concept(client, collection.id, form="tur").status_code == 201


# --------------------------------------------------------------------------
# /stats visibility
# --------------------------------------------------------------------------


def test_stats_exclude_org_private_content_for_outsiders(client):
    root = _register(client, "root")
    anna = _register(client, "anna")
    org = _create_org(client, anna)
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(root)).status_code == 200
    # Org-less public collections are system collections (super admin only)
    # since multi-org — anna's public collection must be org-owned.
    public = _create_collection(client, anna, slug="publik", organisation_id=org["id"])
    private = _create_collection(
        client, anna, slug="internt", organisation_id=org["id"], visibility="org_private"
    )
    _create_concept(client, public["id"], form="öppen", headers=_bearer(anna))
    _create_concept(client, private["id"], form="hemlig", headers=_bearer(anna))

    outsider = client.get("/api/v1/stats", headers=ANON).json()
    assert outsider["collections"] == 1
    assert outsider["concepts"] == 1
    assert outsider["versions"] == 1

    member = client.get("/api/v1/stats", headers=_bearer(anna)).json()
    assert member["collections"] == 2
    assert member["concepts"] == 2
    superset = client.get("/api/v1/stats", headers=_bearer(root)).json()
    assert superset["concepts"] == 2
    # Users count stays global.
    assert outsider["users"] == member["users"] == superset["users"]


# --------------------------------------------------------------------------
# Endorsements
# --------------------------------------------------------------------------


def test_endorsement_rights_and_note_required(client):
    """Endorsement rework 2026-07-11: stamping = admins of an APPROVED org, on
    their own org's behalf, on any visible version — regardless of who owns
    the collection. Super admins do NOT stamp."""
    root, anna, cesar, bertil, coll, a, b, _rel = _org_locked_setup(client)
    version_id = a["head"]["id"]
    payload = {"note": "Fastställd i styrgruppen."}

    # erik is admin of an org that is NOT approved yet → 403 (approval gates
    # stamping; k2 itself is already approved by the setup).
    erik = _register(client, "erik")
    ny_org = _create_org(client, erik, slug="ny-org", name="Ny organisation")
    assert (
        client.post(
            f"/api/v1/versions/{version_id}/endorsements",
            json=payload,
            headers=_bearer(erik),
        ).status_code
        == 403
    )

    # note is REQUIRED (422 both when missing and when empty).
    for body in ({}, {"note": ""}):
        assert (
            client.post(
                f"/api/v1/versions/{version_id}/endorsements",
                json=body,
                headers=_bearer(anna),
            ).status_code
            == 422
        )

    # Rights: org-less stranger and editor member → 403; SUPER ADMIN → 403
    # (an endorsement without an organisation behind it is meaningless);
    # anonymous → 401; unknown version → 404.
    for headers, expected in (
        (_bearer(bertil), 403),
        (_bearer(cesar), 403),
        (_bearer(root), 403),
        (ANON, 401),
    ):
        resp = client.post(
            f"/api/v1/versions/{version_id}/endorsements", json=payload, headers=headers
        )
        assert resp.status_code == expected
    assert (
        client.post(
            "/api/v1/versions/finns-inte/endorsements", json=payload, headers=_bearer(anna)
        ).status_code
        == 404
    )

    # The approved org's admin stamps successfully — on the org's behalf.
    stamped = client.post(
        f"/api/v1/versions/{version_id}/endorsements", json=payload, headers=_bearer(anna)
    )
    assert stamped.status_code == 201, stamped.text
    assert stamped.json()["body"] == "K2 Nationellt kunskapscentrum"
    assert stamped.json()["organisation"]["slug"] == "k2"
    assert stamped.json()["note"] == payload["note"]
    assert stamped.json()["withdrawn_at"] is None

    # Same org, same version again → 409 (already flagged).
    assert (
        client.post(
            f"/api/v1/versions/{version_id}/endorsements",
            json={"note": "Igen."},
            headers=_bearer(anna),
        ).status_code
        == 409
    )

    # CROSS-ORG: another approved org's admin flags the SAME version even
    # though her org does not own the collection — coexistence is the point.
    diana = _register(client, "diana")
    resp = client.post(
        "/api/v1/orgs",
        json={"name": "Trafikverket", "slug": "trafikverket"},
        headers=_bearer(diana),
    )
    assert resp.status_code == 201
    assert (
        client.post("/api/v1/orgs/trafikverket/approve", headers=_bearer(root)).status_code == 200
    )
    cross = client.post(
        f"/api/v1/versions/{version_id}/endorsements",
        json={"note": "Vi använder denna definition."},
        headers=_bearer(diana),
    )
    assert cross.status_code == 201, cross.text
    assert cross.json()["organisation"]["slug"] == "trafikverket"

    # Both stamps surface on the version in the Time Machine payload.
    graph = client.get(f"/api/v1/concepts/{a['id']}/graph").json()
    head = next(v for v in graph["versions"] if v["id"] == version_id)
    assert len(head["endorsements"]) == 2

    # MULTI-ORG: diana invites anna (already a k2 member) as a second admin —
    # holding memberships in several orgs is now allowed (201). With two admin
    # orgs the acting org must be NAMED: no organisation_id → 422 (ambiguous);
    # an org outside her admin set → 403; a named candidate → 201.
    added = client.post(
        "/api/v1/orgs/trafikverket/members",
        json={"handle": "anna", "role": "admin"},
        headers=_bearer(diana),
    )
    assert added.status_code == 201, added.text
    b_version = b["head"]["id"]
    assert (
        client.post(
            f"/api/v1/versions/{b_version}/endorsements",
            json={"note": "Utan avsändare."},
            headers=_bearer(anna),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/versions/{b_version}/endorsements",
            json={"note": "Fel avsändare.", "organisation_id": ny_org["id"]},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    named = client.post(
        f"/api/v1/versions/{b_version}/endorsements",
        json={
            "note": "För K2:s räkning.",
            "organisation_id": stamped.json()["organisation"]["id"],
        },
        headers=_bearer(anna),
    )
    assert named.status_code == 201, named.text
    assert named.json()["organisation"]["slug"] == "k2"


def test_endorsement_moves_within_concept(client):
    """One ACTIVE flag per org and concept: stamping a new version of the same
    concept auto-withdraws the org's previous stamp (record kept)."""
    _root, anna, _cesar, _bertil, _coll, a, _b, _rel = _org_locked_setup(client)
    v1 = a["head"]["id"]
    first = client.post(
        f"/api/v1/versions/{v1}/endorsements",
        json={"note": "Fastställd."},
        headers=_bearer(anna),
    )
    assert first.status_code == 201

    v2 = client.post(
        f"/api/v1/concepts/{a['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": v1,
            "canonical_form": a["head"]["canonical_form"],
            "definition_md": "Ny formulering.",
            "note": "Putsning.",
        },
        headers=_bearer(anna),
    ).json()
    moved = client.post(
        f"/api/v1/versions/{v2['id']}/endorsements",
        json={"note": "Vi går över till den nya formuleringen."},
        headers=_bearer(anna),
    )
    assert moved.status_code == 201

    graph = client.get(f"/api/v1/concepts/{a['id']}/graph").json()
    old = next(v for v in graph["versions"] if v["id"] == v1)
    new = next(v for v in graph["versions"] if v["id"] == v2["id"])
    assert old["endorsements"][0]["withdrawn_at"] is not None
    assert "Ersatt av nytt intyg" in old["endorsements"][0]["withdrawal_note"]
    assert new["endorsements"][0]["withdrawn_at"] is None


def test_endorsement_works_on_orgless_collection_but_not_for_superadmin(client, collection):
    """The owning org is irrelevant for stamping rights — any approved org's
    admin may flag its definition, also in org-less collections. Super admins
    cannot stamp at all."""
    root = _register(client, "root")
    anna = _register(client, "anna")
    _create_org(client, anna)
    client.post("/api/v1/orgs/k2/approve", headers=_bearer(root))
    concept = _create_concept(client, collection.id, headers=_bearer(anna)).json()
    payload = {"note": "Kanonisk definition."}
    stamped = client.post(
        f"/api/v1/versions/{concept['head']['id']}/endorsements",
        json=payload,
        headers=_bearer(anna),
    )
    assert stamped.status_code == 201
    denied = client.post(
        f"/api/v1/versions/{concept['head']['id']}/endorsements",
        json=payload,
        headers=_bearer(root),
    )
    assert denied.status_code == 403


def test_status_filter_endorsed_means_active_endorsement(client):
    """?status=endorsed on the concepts list = "some version carries an ACTIVE
    endorsement" (the value survives the vocabulary removal for URL compat)."""
    _root, anna, _cesar, _bertil, coll, a, b, _rel = _org_locked_setup(client)
    stamped = client.post(
        f"/api/v1/versions/{a['head']['id']}/endorsements",
        json={"note": "Fastställd."},
        headers=_bearer(anna),
    ).json()

    hits = client.get(
        "/api/v1/concepts", params={"status": "endorsed", "collection": coll["slug"]}
    ).json()
    assert [i["canonical_form"] for i in hits["items"]] == [a["head"]["canonical_form"]]

    # Withdrawn stamp → no longer matched.
    client.post(
        f"/api/v1/endorsements/{stamped['id']}/withdraw",
        json={"note": "Återkallad."},
        headers=_bearer(anna),
    )
    hits = client.get(
        "/api/v1/concepts", params={"status": "endorsed", "collection": coll["slug"]}
    ).json()
    assert hits["total"] == 0

    # Combined with a real status the filter is an OR, like before.
    combo = client.get(
        "/api/v1/concepts", params={"status": "draft,endorsed", "collection": coll["slug"]}
    ).json()
    assert combo["total"] == 2  # both drafts; none endorsed


def test_endorsement_withdraw_keeps_record(client):
    root, anna, cesar, bertil, _coll, a, _b, _rel = _org_locked_setup(client)
    version_id = a["head"]["id"]
    stamped = client.post(
        f"/api/v1/versions/{version_id}/endorsements",
        json={"note": "Fastställd."},
        headers=_bearer(anna),
    ).json()

    # Withdrawal: the endorsing org's ADMINS or super admins; note required;
    # never deletes.
    for headers in (_bearer(bertil), _bearer(cesar)):
        assert (
            client.post(
                f"/api/v1/endorsements/{stamped['id']}/withdraw",
                json={"note": "Nej."},
                headers=headers,
            ).status_code
            == 403
        )
    assert (
        client.post(
            f"/api/v1/endorsements/{stamped['id']}/withdraw", json={}, headers=_bearer(anna)
        ).status_code
        == 422
    )
    withdrawn = client.post(
        f"/api/v1/endorsements/{stamped['id']}/withdraw",
        json={"note": "Ersatt av ny formulering."},
        headers=_bearer(anna),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["withdrawn_at"] is not None
    assert withdrawn.json()["withdrawal_note"] == "Ersatt av ny formulering."
    # Idempotence guard: withdrawing twice is a conflict.
    assert (
        client.post(
            f"/api/v1/endorsements/{stamped['id']}/withdraw",
            json={"note": "Igen."},
            headers=_bearer(anna),
        ).status_code
        == 409
    )
    # Super admins can withdraw (abuse handling) even though they cannot stamp.
    second = client.post(
        f"/api/v1/versions/{version_id}/endorsements",
        json={"note": "Igen, efter återkallelsen."},
        headers=_bearer(anna),
    ).json()
    assert (
        client.post(
            f"/api/v1/endorsements/{second['id']}/withdraw",
            json={"note": "Missbruk."},
            headers=_bearer(root),
        ).status_code
        == 200
    )
    # The stamp is still on the version (withdrawn, not deleted).
    graph = client.get(f"/api/v1/concepts/{a['id']}/graph").json()
    head = next(v for v in graph["versions"] if v["id"] == version_id)
    assert head["endorsements"][0]["withdrawn_at"] is not None


# --------------------------------------------------------------------------
# Lock & archive: 423 semantics
# --------------------------------------------------------------------------


def test_patch_lock_archive_requires_manage_rights(client):
    _root, anna, cesar, bertil, coll, _a, _b, _rel = _org_locked_setup(client)
    for headers in (_bearer(bertil), _bearer(cesar)):
        assert (
            client.patch(
                f"/api/v1/collections/{coll['slug']}",
                json={"is_locked": True},
                headers=headers,
            ).status_code
            == 403
        )
    locked = client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_locked": True}, headers=_bearer(anna)
    )
    assert locked.status_code == 200
    assert locked.json()["is_locked"] is True
    assert locked.json()["is_archived"] is False


def test_locked_collection_423_matrix_for_concept_writes(client):
    root, anna, cesar, bertil, coll, a, _b, _rel = _org_locked_setup(client)
    client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_locked": True}, headers=_bearer(anna)
    )

    # Stranger and editor member → 423 with structured detail; org admin + super write on.
    for headers in (_bearer(bertil), _bearer(cesar)):
        resp = _create_concept(client, coll["id"], form="nytt", headers=headers)
        assert resp.status_code == 423
        assert resp.json()["detail"]["code"] == "collection_locked"
    ok_admin = _create_concept(client, coll["id"], form="nytt-1", headers=_bearer(anna))
    assert ok_admin.status_code == 201
    ok_super = _create_concept(client, coll["id"], form="nytt-2", headers=_bearer(root))
    assert ok_super.status_code == 201

    # Version + promote paths share the guard.
    revise = {
        "mode": "revise",
        "base_version_id": a["head"]["id"],
        "canonical_form": "resa",
        "definition_md": "Ny text.",
    }
    assert (
        client.post(
            f"/api/v1/concepts/{a['id']}/versions", json=revise, headers=_bearer(cesar)
        ).status_code
        == 423
    )
    assert (
        client.post(
            f"/api/v1/concepts/{a['id']}/promote",
            json={"version_id": a["head"]["id"]},
            headers=_bearer(cesar),
        ).status_code
        == 423
    )
    new_head = client.post(
        f"/api/v1/concepts/{a['id']}/versions", json=revise, headers=_bearer(anna)
    )
    assert new_head.status_code == 201

    # Unlocking restores editor writes.
    client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_locked": False}, headers=_bearer(anna)
    )
    ok_editor = _create_concept(client, coll["id"], form="nytt-3", headers=_bearer(cesar))
    assert ok_editor.status_code == 201


def test_locked_collection_blocks_relations_and_imports(client):
    _root, anna, cesar, _bertil, coll, a, b, rel_id = _org_locked_setup(client)
    client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_locked": True}, headers=_bearer(anna)
    )
    relation = {
        "relation_type": "broader",
        "from_concept_id": a["id"],
        "to_concept_id": b["id"],
    }
    rows = {"rows": [{"canonical_form": "x", "definition": "En definition."}], "dry_run": True}

    assert (
        client.post("/api/v1/relations", json=relation, headers=_bearer(cesar)).status_code == 423
    )
    assert client.delete(f"/api/v1/relations/{rel_id}", headers=_bearer(cesar)).status_code == 423
    assert (
        client.post(
            f"/api/v1/collections/{coll['slug']}/import-rows",
            json=rows,
            headers=_bearer(cesar),
        ).status_code
        == 423
    )
    # Owning-org admin passes all three.
    assert (
        client.post("/api/v1/relations", json=relation, headers=_bearer(anna)).status_code == 201
    )
    assert client.delete(f"/api/v1/relations/{rel_id}", headers=_bearer(anna)).status_code == 204
    imported = client.post(
        f"/api/v1/collections/{coll['slug']}/import-rows", json=rows, headers=_bearer(anna)
    )
    assert imported.status_code == 200
    assert imported.json()["created"] == 1


def test_archived_collection_blocks_all_writes_and_hides_from_list(client):
    root, anna, cesar, _bertil, coll, a, b, _rel = _org_locked_setup(client)
    client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_archived": True}, headers=_bearer(anna)
    )

    # Archived beats every privilege — even owning-org admin and super admin.
    for headers in (_bearer(cesar), _bearer(anna), _bearer(root)):
        resp = _create_concept(client, coll["id"], form="nytt", headers=headers)
        assert resp.status_code == 423
        assert resp.json()["detail"]["code"] == "collection_archived"
    assert (
        client.post(
            "/api/v1/relations",
            json={
                "relation_type": "broader",
                "from_concept_id": a["id"],
                "to_concept_id": b["id"],
            },
            headers=_bearer(anna),
        ).status_code
        == 423
    )
    assert (
        client.post(
            f"/api/v1/collections/{coll['slug']}/import-rows",
            json={"rows": [{"canonical_form": "x", "definition": "d"}], "dry_run": True},
            headers=_bearer(root),
        ).status_code
        == 423
    )

    # Hidden from the list by default; include_archived=1 shows it; direct GET works.
    slugs = [c["slug"] for c in client.get("/api/v1/collections").json()]
    assert coll["slug"] not in slugs
    slugs = [
        c["slug"] for c in client.get("/api/v1/collections", params={"include_archived": 1}).json()
    ]
    assert coll["slug"] in slugs
    direct = client.get(f"/api/v1/collections/{coll['slug']}")
    assert direct.status_code == 200
    assert direct.json()["is_archived"] is True

    # PATCH stays open (the unarchive path) — then writes work again.
    unarchived = client.patch(
        f"/api/v1/collections/{coll['slug']}", json={"is_archived": False}, headers=_bearer(anna)
    )
    assert unarchived.status_code == 200
    reopened = _create_concept(client, coll["id"], form="nytt", headers=_bearer(anna))
    assert reopened.status_code == 201


# --------------------------------------------------------------------------
# Org suspension
# --------------------------------------------------------------------------


def test_suspended_org_blocks_member_writes(client):
    """Suspension is ORG-SCOPED (multi-org, 2026-07): it blocks writes into
    the suspended org's OWN collections, managing the org and endorsing on
    its behalf — never the members' writes elsewhere."""
    root, anna, cesar, _bertil, coll, a, _b, _rel = _org_locked_setup(client)
    # An unrelated org-less PUBLIC 'anyone' collection (super-admin system
    # collection) to prove the suspension does not follow the member around.
    allman = _create_collection(client, root, slug="allmanningen")

    # Only super admins suspend.
    assert client.post("/api/v1/orgs/k2/suspend", headers=_bearer(anna)).status_code == 403
    suspended = client.post("/api/v1/orgs/k2/suspend", headers=_bearer(root))
    assert suspended.status_code == 200
    assert suspended.json()["is_suspended"] is True

    # Writes into the suspended org's collections → 403 with the org_suspended
    # code; reads still work.
    for headers in (_bearer(anna), _bearer(cesar)):
        resp = _create_concept(client, coll["id"], form="nytt", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "org_suspended"
    assert client.get(f"/api/v1/concepts/{a['id']}", headers=_bearer(anna)).status_code == 200

    # Managing the suspended org as its admin → 403 (super admins only).
    assert (
        client.post(
            "/api/v1/orgs/k2/members",
            json={"handle": "bertil", "role": "viewer"},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    # Endorsing on the suspended org's behalf → 403.
    assert (
        client.post(
            f"/api/v1/versions/{a['head']['id']}/endorsements",
            json={"note": "Fastställd."},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    # But the SAME member still writes in unrelated collections — the old
    # global block is gone.
    elsewhere = _create_concept(client, allman["id"], form="fri", headers=_bearer(anna))
    assert elsewhere.status_code == 201

    # Unsuspend restores writes in the org's own collections.
    restored = client.post("/api/v1/orgs/k2/unsuspend", headers=_bearer(root))
    assert restored.status_code == 200
    assert restored.json()["is_suspended"] is False
    reopened = _create_concept(client, coll["id"], form="nytt", headers=_bearer(anna))
    assert reopened.status_code == 201


# --------------------------------------------------------------------------
# Admin users
# --------------------------------------------------------------------------


def test_admin_users_list_query_and_filters(client):
    root = _register(client, "root")
    anna = _register(client, "anna")
    org = _create_org(client, anna)  # anna becomes org admin (and owner)
    assert client.post("/api/v1/orgs/k2/approve", headers=_bearer(root)).status_code == 200
    coll = _create_collection(client, anna, slug="annas", organisation_id=org["id"])
    _create_concept(client, coll["id"], headers=_bearer(anna))

    # Super admin only.
    assert client.get("/api/v1/admin/users", headers=_bearer(anna)).status_code == 403
    assert client.get("/api/v1/admin/users", headers=ANON).status_code == 401

    users = client.get("/api/v1/admin/users", headers=_bearer(root)).json()
    by_handle = {u["handle"]: u for u in users}
    assert {"root", "anna"} <= set(by_handle)
    # Multi-org: `memberships` is a list of active memberships (was
    # `organisation`); anna holds exactly one, as admin member of k2.
    (membership,) = by_handle["anna"]["memberships"]
    assert membership["slug"] == "k2"
    assert membership["role"] == "admin"
    assert membership["kind"] == "member"
    assert by_handle["root"]["memberships"] == []  # G1: supers hold none
    assert by_handle["anna"]["authored_versions"] == 1
    assert by_handle["anna"]["is_active"] is True
    assert by_handle["anna"]["created_at"]
    assert by_handle["root"]["is_super_admin"] is True

    searched = client.get("/api/v1/admin/users", params={"q": "ann"}, headers=_bearer(root)).json()
    assert [u["handle"] for u in searched] == ["anna"]
    admins = client.get(
        "/api/v1/admin/users", params={"filter": "admins"}, headers=_bearer(root)
    ).json()
    assert {"root", "anna"} <= {u["handle"] for u in admins}
    assert (
        client.get(
            "/api/v1/admin/users", params={"filter": "chefer"}, headers=_bearer(root)
        ).status_code
        == 422
    )

    # Deactivate anna → she shows under filter=inactive, not under active.
    client.patch(
        f"/api/v1/admin/users/{anna['user']['id']}",
        json={"is_active": False},
        headers=_bearer(root),
    )
    inactive = client.get(
        "/api/v1/admin/users", params={"filter": "inactive"}, headers=_bearer(root)
    ).json()
    assert [u["handle"] for u in inactive] == ["anna"]
    active = client.get(
        "/api/v1/admin/users", params={"filter": "active"}, headers=_bearer(root)
    ).json()
    assert "anna" not in {u["handle"] for u in active}


def test_admin_patch_never_self_and_super_admin_toggle(client):
    root = _register(client, "root")
    anna = _register(client, "anna")

    # Self-demotion (and any self-change) is blocked.
    selfie = client.patch(
        f"/api/v1/admin/users/{root['user']['id']}",
        json={"is_super_admin": False},
        headers=_bearer(root),
    )
    assert selfie.status_code == 403
    assert (
        client.patch(
            f"/api/v1/admin/users/{root['user']['id']}",
            json={"is_active": False},
            headers=_bearer(root),
        ).status_code
        == 403
    )

    # Non-super callers are rejected; unknown target 404.
    assert (
        client.patch(
            f"/api/v1/admin/users/{root['user']['id']}",
            json={"is_active": False},
            headers=_bearer(anna),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/admin/users/finns-inte", json={"is_active": False}, headers=_bearer(root)
        ).status_code
        == 404
    )

    # Promoting (and demoting) someone else works.
    promoted = client.patch(
        f"/api/v1/admin/users/{anna['user']['id']}",
        json={"is_super_admin": True},
        headers=_bearer(root),
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_super_admin"] is True
    me = client.get("/api/v1/auth/me", headers=_bearer(anna))
    assert me.json()["is_super_admin"] is True
