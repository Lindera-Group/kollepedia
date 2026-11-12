"""Organisations (iteration 2; multi-org memberships 2026-07).

Membership lives in org_memberships: a user may hold ACTIVE memberships in
many organisations, each with a role (admin/editor/viewer) and a kind
(member/guest — guests can never be admin). Ownership is a separate,
structural thing: organisations.owner_user_id is UNIQUE, so a user owns at
most ONE organisation — the economic-responsibility anchor. Org admins
manage members; super admins approve organisations (confirming the claimed
org_type) and transfer ownership.

Guardrails: super admins hold no memberships (G1); members are end-dated,
never deleted (G2); every super-admin action lands in admin_events (G5).
"""

import re
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import is_org_admin, log_admin_event, membership_for, require_user
from ..errors import api_error
from ..models import (
    MEMBERSHIP_KINDS,
    ORG_ROLES,
    ORG_TYPES,
    Organisation,
    OrgMembership,
    User,
    utcnow,
)
from .auth import normalise_handle

router = APIRouter(prefix="/orgs", tags=["orgs"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100)
    # Claimed at creation, confirmed by a super admin at approval.
    org_type: str | None = None


class MemberAddIn(BaseModel):
    handle: str
    role: str = "viewer"
    kind: str = "member"


class MemberPatchIn(BaseModel):
    role: str | None = None
    kind: str | None = None


class OwnerIn(BaseModel):
    user_id: str


class MyMembershipIn(BaseModel):
    # Per-membership opt-out from the public author page (beslut 4) — the
    # member's own call, not the org admin's.
    is_public: bool


class ApproveIn(BaseModel):
    # Super admin confirms (or corrects) the claimed type at approval.
    org_type: str | None = None


class OrgMemberOut(BaseModel):
    user_id: str
    handle: str
    display_name: str
    role: str
    kind: str = "member"
    is_public: bool = True


class OrgOut(BaseModel):
    id: str
    slug: str
    name: str
    is_approved: bool
    is_suspended: bool = False
    org_type: str | None = None
    owner_user_id: str | None = None
    created_at: datetime
    members: list[OrgMemberOut]


def _org_out(db: Session, org: Organisation) -> OrgOut:
    rows = (
        db.query(OrgMembership, User)
        .join(User, OrgMembership.user_id == User.id)
        .filter(
            OrgMembership.organisation_id == org.id,
            OrgMembership.ended_at.is_(None),
        )
        .order_by(User.display_name.asc())
        .all()
    )
    return OrgOut(
        id=org.id,
        slug=org.slug,
        name=org.name,
        is_approved=org.is_approved,
        is_suspended=org.is_suspended,
        org_type=org.org_type,
        owner_user_id=org.owner_user_id,
        created_at=org.created_at,
        members=[
            OrgMemberOut(
                user_id=u.id,
                handle=u.handle,
                display_name=u.display_name,
                role=m.role,
                kind=m.kind,
                is_public=m.is_public,
            )
            for m, u in rows
        ],
    )


def _get_org(db: Session, slug: str) -> Organisation:
    org = db.query(Organisation).filter(Organisation.slug == slug).first()
    if org is None:
        raise api_error(404, "org_not_found", "Organisation not found.", slug=slug)
    return org


def _require_org_admin(user: User, org: Organisation) -> None:
    if user.is_super_admin:
        return
    if not is_org_admin(user, org.id):
        raise api_error(
            403,
            "org_admin_required",
            "Only the organisation's administrators can do this.",
        )
    if org.is_suspended:
        # Org-scoped suspension: even its admins cannot act for it while
        # suspended — only a super admin can (and can lift the suspension).
        raise api_error(403, "org_suspended", "The organisation is suspended.")


def _validate_role(role: str) -> str:
    if role not in ORG_ROLES:
        raise api_error(
            422,
            "invalid_role",
            f"Invalid role '{role}'.",
            role=role,
            allowed=", ".join(ORG_ROLES),
        )
    return role


def _validate_kind(kind: str) -> str:
    if kind not in MEMBERSHIP_KINDS:
        raise api_error(
            422,
            "invalid_membership_kind",
            f"Invalid membership kind '{kind}'.",
            kind=kind,
            allowed=", ".join(MEMBERSHIP_KINDS),
        )
    return kind


def _validate_org_type(org_type: str) -> str:
    if org_type not in ORG_TYPES:
        raise api_error(
            422,
            "invalid_org_type",
            f"Invalid organisation type '{org_type}'.",
            org_type=org_type,
            allowed=", ".join(ORG_TYPES),
        )
    return org_type


def _admin_count(db: Session, org: Organisation) -> int:
    return (
        db.query(OrgMembership)
        .filter(
            OrgMembership.organisation_id == org.id,
            OrgMembership.role == "admin",
            OrgMembership.ended_at.is_(None),
        )
        .count()
    )


def _owned_org(db: Session, user_id: str) -> Organisation | None:
    return db.query(Organisation).filter(Organisation.owner_user_id == user_id).first()


@router.post("", response_model=OrgOut, status_code=201)
def create_org(
    payload: OrgCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    # One OWNED org per user — memberships in other orgs are unlimited.
    if not user.is_super_admin and _owned_org(db, user.id) is not None:
        raise api_error(
            409,
            "already_owns_org",
            "You already own an organisation; a user can only own one.",
        )
    slug = payload.slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise api_error(
            422,
            "invalid_slug",
            "Invalid slug; use lowercase a-z, digits and hyphens.",
            slug=slug,
        )
    if db.query(Organisation).filter(Organisation.slug == slug).first():
        raise api_error(
            409, "org_slug_taken", "An organisation with this slug already exists.", slug=slug
        )
    if db.query(Organisation).filter(Organisation.name == payload.name.strip()).first():
        raise api_error(
            409,
            "org_name_taken",
            "An organisation with this name already exists.",
            name=payload.name.strip(),
        )
    org_type = _validate_org_type(payload.org_type) if payload.org_type else None
    org = Organisation(
        slug=slug,
        name=payload.name.strip(),
        is_approved=user.is_super_admin,
        org_type=org_type,
        created_by=user.id,
    )
    db.add(org)
    db.flush()
    if user.is_super_admin:
        # G1: a super admin never holds memberships and never owns an org —
        # ownership is assigned afterwards via POST /orgs/{slug}/owner.
        log_admin_event(db, user, "org_created", "organisation", org.id, note=org.slug)
    else:
        org.owner_user_id = user.id
        db.add(
            OrgMembership(
                user_id=user.id,
                organisation_id=org.id,
                role="admin",
                kind="member",
            )
        )
    db.commit()
    return _org_out(db, org)


@router.get("", response_model=list[OrgOut])
def list_orgs(
    db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[OrgOut]:
    if user.is_super_admin:
        orgs = db.query(Organisation).order_by(Organisation.name.asc()).all()
    else:
        org_ids = [m.organisation_id for m in user.memberships if m.ended_at is None]
        orgs = (
            db.query(Organisation)
            .filter(Organisation.id.in_(org_ids))
            .order_by(Organisation.name.asc())
            .all()
            if org_ids
            else []
        )
    return [_org_out(db, org) for org in orgs]


@router.get("/{slug}", response_model=OrgOut)
def get_org(
    slug: str, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> OrgOut:
    org = _get_org(db, slug)
    if not (user.is_super_admin or membership_for(user, org.id) is not None):
        # Hide existence from outsiders.
        raise api_error(404, "org_not_found", "Organisation not found.", slug=slug)
    return _org_out(db, org)


@router.post("/{slug}/approve", response_model=OrgOut)
def approve_org(
    slug: str,
    payload: ApproveIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    if not user.is_super_admin:
        raise api_error(
            403,
            "super_admin_required",
            "Only super administrators can approve organisations.",
        )
    org = _get_org(db, slug)
    if payload is not None and payload.org_type:
        org.org_type = _validate_org_type(payload.org_type)
    org.is_approved = True
    log_admin_event(
        db, user, "org_approved", "organisation", org.id, note=org.org_type or org.slug
    )
    db.commit()
    return _org_out(db, org)


def _require_super(user: User) -> None:
    if not user.is_super_admin:
        raise api_error(
            403,
            "super_admin_required",
            "Only super administrators can suspend or reactivate organisations.",
        )


@router.post("/{slug}/suspend", response_model=OrgOut)
def suspend_org(
    slug: str, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> OrgOut:
    """Suspend an organisation (super admin): writes in the org's context —
    its collections, endorsing on its behalf, managing it — are blocked
    until the org is unsuspended. G2: suspension, never deletion."""
    _require_super(user)
    org = _get_org(db, slug)
    org.is_suspended = True
    log_admin_event(db, user, "org_suspended", "organisation", org.id, note=org.slug)
    db.commit()
    return _org_out(db, org)


@router.post("/{slug}/unsuspend", response_model=OrgOut)
def unsuspend_org(
    slug: str, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> OrgOut:
    _require_super(user)
    org = _get_org(db, slug)
    org.is_suspended = False
    log_admin_event(db, user, "org_unsuspended", "organisation", org.id, note=org.slug)
    db.commit()
    return _org_out(db, org)


@router.post("/{slug}/owner", response_model=OrgOut)
def transfer_owner(
    slug: str,
    payload: OwnerIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    """Ownership transfer (super admin): the target must not be a super admin
    (G1) and must not already own another organisation. An active admin
    membership is ensured — the owner is always an admin member."""
    _require_super(user)
    org = _get_org(db, slug)
    target = db.get(User, payload.user_id)
    if target is None:
        raise api_error(404, "user_not_found", "User not found.", user_id=payload.user_id)
    if target.is_super_admin:
        raise api_error(
            409,
            "super_admin_cannot_own_org",
            "A super administrator cannot own an organisation.",
        )
    already = _owned_org(db, target.id)
    if already is not None and already.id != org.id:
        raise api_error(
            409,
            "target_already_owns_org",
            f"{target.display_name} already owns the organisation {already.name}.",
            display_name=target.display_name,
            org_name=already.name,
        )
    membership = membership_for(target, org.id)
    if membership is None:
        db.add(
            OrgMembership(
                user_id=target.id,
                organisation_id=org.id,
                role="admin",
                kind="member",
                invited_by=user.id,
            )
        )
    else:
        membership.role = "admin"
        membership.kind = "member"
    org.owner_user_id = target.id
    log_admin_event(
        db, user, "org_owner_transferred", "organisation", org.id, note=target.handle
    )
    db.commit()
    return _org_out(db, org)


@router.patch("/{slug}/my-membership", response_model=OrgOut)
def patch_my_membership(
    slug: str,
    payload: MyMembershipIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    """The member's own visibility switch: show or hide this membership on
    the public author page. Not an admin surface on purpose."""
    org = _get_org(db, slug)
    membership = _get_membership(db, org, user.id)
    membership.is_public = payload.is_public
    db.commit()
    return _org_out(db, org)


@router.post("/{slug}/members", response_model=OrgOut, status_code=201)
def add_member(
    slug: str,
    payload: MemberAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    org = _get_org(db, slug)
    _require_org_admin(user, org)
    role = _validate_role(payload.role)
    kind = _validate_kind(payload.kind)
    if kind == "guest" and role == "admin":
        raise api_error(
            422,
            "guest_cannot_be_admin",
            "A guest cannot be an administrator; change kind to member first.",
        )
    handle = normalise_handle(payload.handle)
    target = db.query(User).filter(User.handle == handle).first()
    if target is None:
        raise api_error(
            404, "user_not_found", f"No user with handle '{handle}' exists.", handle=handle
        )
    if target.is_super_admin:
        # G1: super admins hold no memberships — they never speak for an org.
        raise api_error(
            409,
            "super_admin_cannot_be_member",
            "A super administrator cannot be a member of an organisation.",
        )
    if membership_for(target, org.id) is not None:
        raise api_error(
            409,
            "already_member",
            f"{target.display_name} is already a member of the organisation.",
            display_name=target.display_name,
        )
    db.add(
        OrgMembership(
            user_id=target.id,
            organisation_id=org.id,
            role=role,
            kind=kind,
            invited_by=user.id,
        )
    )
    db.commit()
    return _org_out(db, org)


def _get_membership(db: Session, org: Organisation, user_id: str) -> OrgMembership:
    membership = (
        db.query(OrgMembership)
        .filter(
            OrgMembership.organisation_id == org.id,
            OrgMembership.user_id == user_id,
            OrgMembership.ended_at.is_(None),
        )
        .first()
    )
    if membership is None:
        raise api_error(
            404,
            "member_not_found",
            "The user is not a member of the organisation.",
            user_id=user_id,
        )
    return membership


@router.patch("/{slug}/members/{user_id}", response_model=OrgOut)
def patch_member(
    slug: str,
    user_id: str,
    payload: MemberPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> OrgOut:
    org = _get_org(db, slug)
    _require_org_admin(user, org)
    membership = _get_membership(db, org, user_id)
    role = _validate_role(payload.role) if payload.role is not None else membership.role
    kind = _validate_kind(payload.kind) if payload.kind is not None else membership.kind
    if kind == "guest" and role == "admin":
        raise api_error(
            422,
            "guest_cannot_be_admin",
            "A guest cannot be an administrator; change kind to member first.",
        )
    if org.owner_user_id == user_id and (role != "admin" or kind != "member"):
        raise api_error(
            409,
            "owner_must_be_admin",
            "The owner must be an administrator and a member; transfer ownership first.",
        )
    if membership.role == "admin" and role != "admin" and _admin_count(db, org) <= 1:
        raise api_error(
            409, "last_admin", "The organisation must have at least one administrator."
        )
    membership.role = role
    membership.kind = kind
    db.commit()
    return _org_out(db, org)


@router.delete("/{slug}/members/{user_id}", status_code=204)
def remove_member(
    slug: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """End a membership (G2: end-dated, never deleted — re-invitation creates
    a fresh row)."""
    org = _get_org(db, slug)
    _require_org_admin(user, org)
    membership = _get_membership(db, org, user_id)
    if org.owner_user_id == user_id:
        raise api_error(
            409,
            "owner_cannot_be_removed",
            "The owner cannot be removed from the organisation; transfer ownership first.",
        )
    if membership.role == "admin" and _admin_count(db, org) <= 1:
        raise api_error(
            409, "last_admin", "The organisation must have at least one administrator."
        )
    membership.ended_at = utcnow()
    db.commit()
