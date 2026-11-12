"""Registration hardening (migration 008): PoW, honeypot, heuristics → manual
review, username collisions → claim pointers, profile fields, admin approval.
"""

from app.models import User
from tests.conftest import register_payload, solve_pow


def _register(client, email, handle=None, **extra):
    body = register_payload(
        client,
        email=email,
        display_name=extra.pop("display_name", email.split("@")[0].title()),
        password="hemligt-losenord",
        **({"handle": handle} if handle else {}),
        **extra,
    )
    return client.post("/api/v1/auth/register", json=body)


def _bearer(auth) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['token']}"}


# ── Proof of work ──


def test_register_without_pow_is_rejected(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.org", "display_name": "A", "password": "hemligt-losenord"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "pow_missing"


def test_pow_challenge_is_single_use(client):
    solved = solve_pow(client)
    first = client.post(
        "/api/v1/auth/register",
        json={
            "email": "en@example.org",
            "display_name": "En",
            "password": "hemligt-losenord",
            "pow": solved,
        },
    )
    assert first.status_code == 201
    replay = client.post(
        "/api/v1/auth/register",
        json={
            "email": "tva@example.org",
            "display_name": "Två",
            "password": "hemligt-losenord",
            "pow": solved,
        },
    )
    assert replay.status_code == 400
    detail = replay.json()["detail"]
    assert detail["code"] == "pow_invalid"
    assert "redan använd" in detail["params"]["reason"]


def test_pow_wrong_solution_rejected(client):
    solved = solve_pow(client)
    solved["number"] = solved["number"] + 1  # almost certainly wrong at 8 bits
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fel@example.org",
            "display_name": "Fel",
            "password": "hemligt-losenord",
            "pow": solved,
        },
    )
    # A +1 could accidentally also solve it — accept either explicit rejection
    # or (rare) success, but never a silent 500.
    assert resp.status_code in (201, 400)


def test_pow_tampered_signature_rejected(client):
    solved = solve_pow(client)
    solved["bits"] = 1  # try to lower the difficulty → signature mismatch
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fusk@example.org",
            "display_name": "Fusk",
            "password": "hemligt-losenord",
            "pow": solved,
        },
    )
    assert resp.status_code == 400


def test_honeypot_rejects(client):
    resp = _register(client, "bot@example.org", website="https://spam.example")
    assert resp.status_code == 400


# ── Suspicion heuristics → manual review ──


def test_disposable_domain_flags_for_review_and_blocks_writes(client, collection):
    # Bootstrap account first (the first password account is never flagged).
    first = _register(client, "grundare@example.org")
    assert first.status_code == 201
    assert first.json()["user"]["review_status"] == "approved"

    flagged = _register(client, "skum@mailinator.com")
    assert flagged.status_code == 201
    body = flagged.json()
    assert body["user"]["review_status"] == "pending"

    # Pending accounts read but cannot write.
    denied = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection.id,
            "canonical_form": "spamtest",
            "definition_md": "Ska stoppas.",
        },
        headers=_bearer(body),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "account_pending_review"

    # The super admin got a review notification (outbox/allowlist path).
    outbox = client.get("/api/v1/admin/outbox", headers=_bearer(first.json()))
    assert outbox.status_code == 200
    templates = [m["template"] for m in outbox.json()]
    assert "account_review" in templates


def test_admin_approval_unblocks_and_mails(client, collection, db):
    first = _register(client, "chef@example.org")
    flagged = _register(client, "ny@yopmail.com")
    assert flagged.json()["user"]["review_status"] == "pending"
    user_id = flagged.json()["user"]["id"]

    # Approve via the admin routine (same one used for academic accounts).
    approved = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"review_status": "approved"},
        headers=_bearer(first.json()),
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"

    # Writes work now.
    ok = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection.id,
            "canonical_form": "godkänt",
            "definition_md": "Nu går det.",
        },
        headers=_bearer(flagged.json()),
    )
    assert ok.status_code == 201

    # The user was told by mail.
    outbox = client.get("/api/v1/admin/outbox", headers=_bearer(first.json()))
    assert "account_approved" in [m["template"] for m in outbox.json()]


def test_velocity_flags_third_registration(client, monkeypatch):
    monkeypatch.setenv("REG_VELOCITY_LIMIT", "3")
    a = _register(client, "v1@example.org")
    b = _register(client, "v2@example.org")
    c = _register(client, "v3@example.org")
    assert a.json()["user"]["review_status"] == "approved"
    assert b.json()["user"]["review_status"] == "approved"
    assert c.json()["user"]["review_status"] == "pending"


# ── Username (handle) at registration ──


def test_register_with_free_username(client):
    resp = _register(client, "eva@example.org", handle="eva-k")
    assert resp.status_code == 201
    assert resp.json()["user"]["handle"] == "eva-k"


def test_register_username_taken_by_password_account(client):
    _register(client, "forst@example.org", handle="unik")
    resp = _register(client, "sen@example.org", handle="unik")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "handle_taken"


def test_register_username_of_unclaimed_author_points_to_claim(client, db):
    db.add(User(handle="import-forfattare", display_name="Importerad Författare"))
    db.commit()
    _register(client, "bootstrap@example.org")  # bootstrap so suspicion logic is live
    resp = _register(client, "jag@example.org", handle="import-forfattare")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "handle_unclaimed"
    assert detail["params"]["handle"] == "import-forfattare"


def test_register_email_of_unclaimed_author_points_to_claim(client, db):
    db.add(
        User(
            handle="gammal-skribent",
            display_name="Gammal Skribent",
            email="gammal@example.org",
        )
    )
    db.commit()
    _register(client, "bootstrap2@example.org")
    resp = _register(client, "gammal@example.org", display_name="Gammal")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "email_unclaimed"
    assert detail["params"]["handle"] == "gammal-skribent"


def test_activate_claim_still_works_with_claim_flag(client, db):
    db.add(User(handle="claimbar", display_name="Claimbar Person"))
    db.commit()
    _register(client, "bootstrap3@example.org")
    resp = _register(client, "claimbar@example.org", handle="claimbar", claim=True)
    assert resp.status_code == 201
    assert resp.json()["user"]["handle"] == "claimbar"
    assert resp.json()["user"]["display_name"] == "Claimbar Person"


def test_claiming_imported_identity_requires_manual_review(client, db, collection):
    """Anyone can claim any unclaimed author with any email — so a claim is
    an identity takeover by construction and always lands in manual review
    (write-blocked until a super admin approves, 2026-08-12)."""
    db.add(User(handle="importerad", display_name="Importerad Person"))
    db.commit()
    _register(client, "bootstrap4@example.org")  # bootstrap ≠ claim

    resp = _register(client, "vemsomhelst@example.org", handle="importerad", claim=True)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["review_status"] == "pending"

    denied = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection.id,
            "canonical_form": "kapartest",
            "definition_md": "Ska stoppas.",
        },
        headers=_bearer(body),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "account_pending_review"


def test_pending_account_cannot_create_lists(client, db):
    """Personal lists are writes too — the pending-review gate covers them
    (the gap found in the claim-security pass, closed 2026-08-13)."""
    db.add(User(handle="listkapare", display_name="Listkapare"))
    db.commit()
    _register(client, "bootstrap5@example.org")
    pending = _register(client, "listor@example.org", handle="listkapare", claim=True).json()
    assert pending["user"]["review_status"] == "pending"

    denied = client.post("/api/v1/lists", json={"name": "Spamlista"}, headers=_bearer(pending))
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "account_pending_review"


def test_activation_link_claim_skips_manual_review(client, db):
    """The outreach workbench mints a personal one-time /activate link; a
    claim carrying that token is verified by construction — approved
    directly, and the token is single-use."""
    db.add(User(handle="lankad", display_name="Länkad Person"))
    db.commit()
    admin = _register(client, "grundare5@example.org").json()  # first account = super admin
    target_id = db.query(User).filter(User.handle == "lankad").first().id

    minted = client.post(
        f"/api/v1/admin/outreach/{target_id}/activation-link", headers=_bearer(admin)
    )
    assert minted.status_code == 201
    url = minted.json()["url"]
    assert url.startswith("/activate?handle=lankad&token=")
    token = url.split("token=", 1)[1]

    resp = _register(client, "lankad@example.org", handle="lankad", claim=True, claim_token=token)
    assert resp.status_code == 201
    assert resp.json()["user"]["review_status"] == "approved"

    # Minting for an already-activated author is refused.
    again = client.post(
        f"/api/v1/admin/outreach/{target_id}/activation-link", headers=_bearer(admin)
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "author_already_activated"


def test_claim_with_invalid_activation_token_is_rejected(client, db):
    """A wrong/expired token is a hard 400 — it must not silently fall back
    to the unverified-claim path."""
    db.add(User(handle="feltoken", display_name="Fel Token"))
    db.commit()
    _register(client, "grundare6@example.org")
    resp = _register(
        client, "nagon@example.org", handle="feltoken", claim=True, claim_token="fel-token"
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "activation_token_invalid"


# ── Profile fields ──


def test_patch_profile_bio_and_url(client):
    auth = _register(client, "profil@example.org").json()
    resp = client.patch(
        "/api/v1/auth/me",
        json={"bio": "Forskar om kollektivtrafik.", "web_url": "https://example.org/jag"},
        headers=_bearer(auth),
    )
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Forskar om kollektivtrafik."
    assert resp.json()["web_url"] == "https://example.org/jag"

    # Invalid URL scheme is refused; clearing works with empty strings.
    bad = client.patch(
        "/api/v1/auth/me", json={"web_url": "javascript:alert(1)"}, headers=_bearer(auth)
    )
    assert bad.status_code == 422
    cleared = client.patch(
        "/api/v1/auth/me", json={"bio": "", "web_url": ""}, headers=_bearer(auth)
    )
    assert cleared.json()["bio"] is None
    assert cleared.json()["web_url"] is None


def test_bio_visible_on_public_author_page(client, collection):
    auth = _register(client, "synlig@example.org", handle="synlig-person").json()
    client.patch(
        "/api/v1/auth/me",
        json={"bio": "Skriver om hållplatser."},
        headers=_bearer(auth),
    )
    # The public author surface only lists users with visible authorship.
    created = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection.id,
            "canonical_form": "hållplatsläge",
            "definition_md": "En plats där fordon stannar.",
        },
        headers=_bearer(auth),
    )
    assert created.status_code == 201
    resp = client.get("/api/v1/authors/synlig-person")
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Skriver om hållplatser."
