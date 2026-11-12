"""Admin: user management + password-reset links (iteration 3, super admin only).

- GET   /admin/users?q=&filter=all|active|inactive|admins — full user list
  incl. email/org/role/is_active/created_at/authored version counts.
- PATCH /admin/users/{id} {is_active?, is_super_admin?} — never on yourself
  (no self-demotion, no self-lockout).
- POST  /admin/users/{id}/reset-link → {url, expires_at}: a one-time 24-hour
  reset token, handed over manually (no email infra). The URL is a relative
  path — the frontend prefixes its own origin.
- GET   /admin/outbox?limit= (iteration 4) — every email the system produced,
  newest first, including 'blocked' and 'outbox' ones (audit surface for the
  allowlist safety net in app/email.py).
"""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import email as email_service
from ..db import get_db
from ..deps import active_memberships, log_admin_event
from ..errors import api_error
from ..models import (
    AdminEvent,
    EmailMessage,
    OrgMembership,
    ResetToken,
    User,
    Version,
    utcnow,
)
from .auth import hash_token, revoke_all_refresh_tokens
from .authors_admin import require_super_admin

router = APIRouter(prefix="/admin", tags=["admin"])

RESET_TTL = timedelta(hours=24)

FILTERS = ("all", "active", "inactive", "admins", "pending")


class AdminUserOrgOut(BaseModel):
    id: str
    slug: str
    name: str
    role: str
    kind: str = "member"
    is_public: bool = True


class AdminUserOut(BaseModel):
    id: str
    handle: str
    display_name: str
    email: str | None = None
    affiliation: str | None = None
    is_active: bool = True
    is_super_admin: bool = False
    review_status: str = "approved"
    review_reason: str | None = None
    created_at: datetime
    memberships: list[AdminUserOrgOut] = []
    authored_versions: int = 0


class AdminUserPatchIn(BaseModel):
    is_active: bool | None = None
    is_super_admin: bool | None = None
    # Manual account review (migration 008): 'approved' unblocks writes and
    # mails the user; 'rejected' blocks writes permanently. The same routine
    # is used for validating academic-organisation accounts.
    review_status: str | None = None


class ResetLinkOut(BaseModel):
    url: str
    expires_at: datetime


def _admin_user_out(user: User, authored: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        email=user.email,
        affiliation=user.affiliation,
        is_active=user.is_active,
        is_super_admin=user.is_super_admin,
        review_status=user.review_status,
        review_reason=user.review_reason,
        created_at=user.created_at,
        memberships=[
            AdminUserOrgOut(
                id=m.organisation.id,
                slug=m.organisation.slug,
                name=m.organisation.name,
                role=m.role,
                kind=m.kind,
                is_public=m.is_public,
            )
            for m in active_memberships(user)
        ],
        authored_versions=authored,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str = "",
    filter: str = Query(default="all"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> list[AdminUserOut]:
    if filter not in FILTERS:
        raise api_error(
            422,
            "invalid_filter",
            f"Invalid filter '{filter}' — allowed: {', '.join(FILTERS)}.",
            filter=filter,
            allowed=", ".join(FILTERS),
        )
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.handle.ilike(like),
                User.display_name.ilike(like),
                User.email.ilike(like),
            )
        )
    if filter == "active":
        query = query.filter(User.is_active.is_(True))
    elif filter == "inactive":
        query = query.filter(User.is_active.is_(False))
    elif filter == "admins":
        admin_member_ids = (
            db.query(OrgMembership.user_id)
            .filter(OrgMembership.role == "admin", OrgMembership.ended_at.is_(None))
            .scalar_subquery()
        )
        query = query.filter(
            or_(User.is_super_admin.is_(True), User.id.in_(admin_member_ids))
        )
    elif filter == "pending":
        query = query.filter(User.review_status == "pending")
    users = query.order_by(User.display_name.asc()).limit(limit).all()

    authored: dict[str, int] = {}
    user_ids = [u.id for u in users]
    if user_ids:
        rows = (
            db.query(Version.created_by, func.count(Version.id))
            .filter(Version.created_by.in_(user_ids))
            .group_by(Version.created_by)
            .all()
        )
        authored = dict(rows)
    return [_admin_user_out(u, authored.get(u.id, 0)) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user(
    user_id: str,
    payload: AdminUserPatchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> AdminUserOut:
    target = db.get(User, user_id)
    if target is None:
        raise api_error(404, "user_not_found", "User not found.")
    if target.id == admin.id:
        raise api_error(
            403,
            "cannot_modify_self",
            "You cannot change your own account — ask another super admin.",
        )
    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data:
        target.is_active = bool(data["is_active"])
        if not target.is_active:
            # Deactivation kills live sessions too.
            revoke_all_refresh_tokens(db, target.id)
        log_admin_event(
            db,
            admin,
            "user_suspended" if not target.is_active else "user_restored",
            "user",
            target.id,
            note=target.handle,
        )
    if "is_super_admin" in data:
        grant = bool(data["is_super_admin"])
        if grant and active_memberships(target):
            # G1: a super admin holds no memberships — they never speak for
            # an organisation. End the memberships first, then grant.
            raise api_error(
                409,
                "superadmin_has_memberships",
                "User has active organisation memberships — end them before "
                "the account becomes super admin.",
            )
        if not grant and target.is_super_admin:
            remaining = db.query(User).filter(User.is_super_admin.is_(True)).count()
            if remaining <= 1:
                # G3: never demote the last super admin.
                raise api_error(
                    409,
                    "last_super_admin",
                    "There must be at least one super admin.",
                )
        target.is_super_admin = grant
        log_admin_event(
            db,
            admin,
            "superadmin_granted" if grant else "superadmin_revoked",
            "user",
            target.id,
            note=target.handle,
        )
    if "review_status" in data and data["review_status"] is not None:
        status = data["review_status"]
        if status not in ("approved", "pending", "rejected"):
            raise api_error(422, "invalid_review_status", "Invalid review status.", status=status)
        was_pending = target.review_status == "pending"
        target.review_status = status
        if status == "approved":
            target.review_reason = None
            if was_pending and target.email:
                email_service.send(
                    db,
                    to_addr=target.email,
                    subject="Kollepedia: ditt konto är godkänt",
                    body_text=(
                        f"Hej {target.display_name}!\n\n"
                        "Granskningen av ditt konto är klar – det är nu godkänt "
                        "och du kan bidra fullt ut.\n\nVälkommen!"
                    ),
                    template="account_approved",
                )
    db.commit()
    authored = (
        db.query(func.count(Version.id)).filter(Version.created_by == target.id).scalar() or 0
    )
    return _admin_user_out(target, authored)


@router.post("/users/{user_id}/reset-link", response_model=ResetLinkOut, status_code=201)
def create_reset_link(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> ResetLinkOut:
    target = db.get(User, user_id)
    if target is None:
        raise api_error(404, "user_not_found", "User not found.")
    if not target.is_active:
        raise api_error(
            403, "account_suspended", "Account is suspended — activate it before resetting."
        )
    raw = secrets.token_urlsafe(32)
    expires_at = utcnow() + RESET_TTL
    db.add(ResetToken(user_id=target.id, token_hash=hash_token(raw), expires_at=expires_at))
    db.commit()
    # Relative path by design: the frontend prefixes its own origin.
    return ResetLinkOut(url=f"/reset?token={raw}", expires_at=expires_at)


# ── Guardrail G5: super-admin audit log ──


class AdminEventOut(BaseModel):
    id: str
    actor_id: str
    actor_handle: str | None = None
    action: str
    target_type: str
    target_id: str
    note: str | None = None
    created_at: datetime


@router.get("/events", response_model=list[AdminEventOut])
def list_admin_events(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> list[AdminEventOut]:
    rows = (
        db.query(AdminEvent, User.handle)
        .outerjoin(User, AdminEvent.actor_id == User.id)
        .order_by(AdminEvent.created_at.desc(), AdminEvent.id.desc())
        .limit(limit)
        .all()
    )
    return [
        AdminEventOut(
            id=e.id,
            actor_id=e.actor_id,
            actor_handle=handle,
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            note=e.note,
            created_at=e.created_at,
        )
        for e, handle in rows
    ]


# ── Iteration 4: email outbox ──


class OutboxMessageOut(BaseModel):
    id: str
    to_addr: str
    subject: str
    body_text: str
    template: str
    status: str
    created_at: datetime
    sent_at: datetime | None = None


@router.get("/outbox", response_model=list[OutboxMessageOut])
def list_outbox(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> list[OutboxMessageOut]:
    messages = (
        db.query(EmailMessage)
        .order_by(EmailMessage.created_at.desc(), EmailMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [
        OutboxMessageOut(
            id=m.id,
            to_addr=m.to_addr,
            subject=m.subject,
            body_text=m.body_text,
            template=m.template,
            status=m.status,
            created_at=m.created_at,
            sent_at=m.sent_at,
        )
        for m in messages
    ]
