"""scripts/ops.py — the super admin's hands inside the container."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import select

from app.models import Organisation, OrgMembership, ResetToken, User
from app.routers.auth import hash_token

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _ops():
    spec = importlib.util.spec_from_file_location("ops", SCRIPTS / "ops.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _org(db, slug="svensk-kollektivtrafik", name="Svensk Kollektivtrafik") -> Organisation:
    org = Organisation(slug=slug, name=name, is_approved=True, org_type="industry_association")
    db.add(org)
    db.commit()
    return org


def test_provision_user_creates_verified_passwordless_member_with_reset_link(db) -> None:
    ops = _ops()
    org = _org(db)

    result = ops.provision_user(
        db,
        display_name="Jonas Johansson",
        email="Jonas@Example.org",
        org_slug=org.slug,
        role="admin",
        owner=True,
        origin="https://staging.example",
    )

    user = db.scalar(select(User).where(User.handle == "jonas-johansson"))
    assert user is not None
    assert result["created"] is True and result["membership_created"] is True
    assert user.email == "jonas@example.org"
    assert user.email_verified is True
    # Not NULL (a NULL hash is a claimable author profile), not a usable password.
    assert user.password_hash is not None and user.password_hash.startswith("$argon2")
    assert user.review_status == "approved"
    assert user.affiliation == "Svensk Kollektivtrafik"
    membership = db.scalar(select(OrgMembership).where(OrgMembership.user_id == user.id))
    assert membership is not None and membership.role == "admin" and membership.kind == "member"
    db.refresh(org)
    assert org.owner_user_id == user.id

    link = result["reset_link"]
    assert link.startswith("https://staging.example/reset?token=")
    raw = link.split("token=", 1)[1]
    token = db.scalar(select(ResetToken).where(ResetToken.token_hash == hash_token(raw)))
    assert token is not None and token.user_id == user.id and token.consumed_at is None
    # The report never prints the full address.
    text = ops.report(db)
    assert "jonas-johansson" in text and "j***@example.org" in text
    assert "jonas@example.org" not in text


def test_provision_user_is_idempotent_and_can_change_role(db) -> None:
    ops = _ops()
    org = _org(db)
    first = ops.provision_user(
        db, display_name="Mattias Andersson", email="m@example.org", org_slug=org.slug
    )
    second = ops.provision_user(
        db,
        display_name="Mattias Andersson",
        email="m@example.org",
        org_slug=org.slug,
        role="admin",
    )

    assert first["created"] is True and second["created"] is False
    assert second["membership_created"] is False
    users = db.scalars(select(User).where(User.email == "m@example.org")).all()
    assert len(users) == 1
    membership = db.scalar(select(OrgMembership).where(OrgMembership.user_id == users[0].id))
    assert membership is not None and membership.role == "admin"


def test_provision_user_requires_an_existing_organisation(db) -> None:
    ops = _ops()
    try:
        ops.provision_user(db, display_name="X Y", email="x@example.org", org_slug="saknas")
    except SystemExit as exc:
        assert "saknas" in str(exc)
    else:
        raise AssertionError("expected SystemExit for a missing organisation")


def test_reset_link_invalidates_earlier_tokens_and_refuses_super_admins(db) -> None:
    ops = _ops()
    org = _org(db)
    first = ops.provision_user(
        db, display_name="Eva Ek", email="eva@example.org", org_slug=org.slug
    )
    user = db.scalar(select(User).where(User.email == "eva@example.org"))
    assert user is not None
    second = ops.reset_link(db, user.handle, "https://x")

    raw_first = first["reset_link"].split("token=", 1)[1]
    raw_second = second.split("token=", 1)[1]
    t1 = db.scalar(select(ResetToken).where(ResetToken.token_hash == hash_token(raw_first)))
    t2 = db.scalar(select(ResetToken).where(ResetToken.token_hash == hash_token(raw_second)))
    assert t1 is not None and t1.consumed_at is not None  # superseded
    assert t2 is not None and t2.consumed_at is None

    user.is_super_admin = True
    db.commit()
    try:
        ops.reset_link(db, user.handle, "https://x")
    except SystemExit as exc:
        assert "superadmin" in str(exc)
    else:
        raise AssertionError("expected SystemExit for a super-admin target")
