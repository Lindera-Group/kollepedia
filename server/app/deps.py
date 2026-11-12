"""Shared dependencies: identity resolution and collection authorisation.

Identity is two-tier (iteration 2, hardened iteration 3):
- Real auth: `Authorization: Bearer <JWT>` (HS256, 12-hour exp, sub = user id)
  plus a rotating httpOnly refresh cookie handled in routers/auth.py.
- Dev fallback: `X-User: <handle>` names the acting user (resolved or created
  on the fly) — honoured only when env DEV_AUTH=1. Off by default: a server
  started without configuration must never accept a bare header as identity
  (local development and the test suite set DEV_AUTH=1 explicitly).

When DEV_AUTH is off the instance is presumably real, so JWT_SECRET must be a
strong value: `require_strong_jwt_secret` (called from the lifespan) refuses
to start on a missing, dev-default or short secret instead of warning.

Authorisation helpers answer three distinct questions about a collection:
- can_view_collection: may the caller read it at all? (org_private hiding)
- can_edit_collection: may the caller write concepts/versions into it?
- can_manage_collection: may the caller change the collection's metadata?

Iteration 3 adds the central write guard `ensure_write_allowed` (inactive account,
suspended organisation, archived/locked collection, edit rights) shared by
concepts, versions, promote, relations and imports.
"""

import os
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header
from sqlalchemy import ColumnElement, or_, true
from sqlalchemy.orm import Session

from .db import get_db
from .errors import api_error
from .models import AdminEvent, Collection, OrgMembership, User

DEV_JWT_SECRET = "kollepedia-dev-secret-do-not-use-in-prod"
JWT_SECRET = os.getenv("JWT_SECRET", DEV_JWT_SECRET)
JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=12)
# Anything shorter is guessable in practice; 32 chars matches `openssl rand
# -hex 16` / `secrets.token_urlsafe(24)`, the smallest values ops generate.
MIN_JWT_SECRET_LENGTH = 32


def dev_auth_enabled() -> bool:
    """X-User dev fallback is only honoured when DEV_AUTH=1 — off by default."""
    return os.getenv("DEV_AUTH", "0") == "1"


def require_strong_jwt_secret() -> None:
    """Fail closed at startup: with the dev fallback off, a missing (= dev
    default), known-dev or short JWT_SECRET would let anyone mint a token for
    any user, so the process refuses to start rather than warn. Raises
    SystemExit so uvicorn/compose report an unhealthy container."""
    if dev_auth_enabled():
        return
    if JWT_SECRET == DEV_JWT_SECRET or len(JWT_SECRET) < MIN_JWT_SECRET_LENGTH:
        raise SystemExit("JWT_SECRET must be set to a strong value when DEV_AUTH is off")


def create_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    """Return the user id (sub) or None. Never raises — bad tokens degrade to
    anonymous instead of 500 (404-safe decode)."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    except Exception:
        # Older PyJWT raised non-PyJWTError exceptions on a mangled header
        # segment (PYSEC-2026-4142); a forged token must never become a 500.
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None


def resolve_identity(
    db: Session, *, token: str | None = None, handle: str | None = None
) -> User | None:
    """The shared identity core behind HTTP headers and WebSocket query params.

    A *present* token always wins and never falls back to the handle — an
    invalid token degrades to anonymous, exactly like `current_user`. The
    handle path is the X-User dev fallback (resolved or created on the fly),
    honoured only when DEV_AUTH=1.
    """
    if token is not None:
        user_id = decode_token(token)
        return db.get(User, user_id) if user_id else None
    if not handle or not dev_auth_enabled():
        return None
    normalized = handle.strip().lower().replace(" ", "-")
    if not normalized:
        return None
    user = db.query(User).filter(User.handle == normalized).first()
    if user is None:
        user = User(handle=normalized, display_name=handle.strip())
        db.add(user)
        db.flush()
    return user


def current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_user: str | None = Header(default=None),
) -> User | None:
    # 1) Real auth: Bearer token wins whenever present.
    if authorization and authorization.lower().startswith("bearer "):
        return resolve_identity(db, token=authorization[7:].strip())
    # 2) Dev fallback: bare handle — only when DEV_AUTH=1 (iteration 3 gating).
    return resolve_identity(db, handle=x_user)


def resolve_ws_user(token: str | None, who: str | None, db: Session) -> User | None:
    """WebSocket identity (app/realtime.py): browsers cannot set headers on a
    WebSocket handshake, so credentials arrive as query params — `?token=<jwt>`
    (wins whenever present) or `?who=<handle>` (the X-User dev fallback,
    DEV_AUTH=1 only)."""
    if token:
        return resolve_identity(db, token=token)
    return resolve_identity(db, handle=who)


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise api_error(401, "login_required", "Login required.")
    if not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    return user


def ensure_actor_can_write(user: User) -> None:
    """Actor-level write gate (iteration 3): inactive accounts cannot write
    anywhere. Accounts flagged for manual review at registration
    (migration 008) can read but not write until a super admin approves
    them — the history is immutable, so junk must be stopped before it
    enters. Org suspension is NOT global (multi-org, 2026-07): it blocks
    writes only in the suspended org's context — enforced per collection
    in ensure_write_allowed and per acting org in endorsements/orgs."""
    if not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    if getattr(user, "review_status", "approved") == "pending":
        raise api_error(
            403,
            "account_pending_review",
            "Account is pending manual review — reading is allowed but "
            "writing requires an administrator's approval.",
        )
    if getattr(user, "review_status", "approved") == "rejected":
        raise api_error(403, "account_suspended", "Account is suspended.")


# ── Membership helpers (multi-org, 2026-07) ──


def active_memberships(user: User) -> list[OrgMembership]:
    """The user's ACTIVE membership rows (ended_at IS NULL). The membership
    count per user is tiny, so scanning the relationship beats a query."""
    return [m for m in user.memberships if m.ended_at is None]


def membership_for(user: User, org_id: str | None) -> OrgMembership | None:
    if not org_id:
        return None
    for m in active_memberships(user):
        if m.organisation_id == org_id:
            return m
    return None


def user_org_ids(user: User, *, roles: tuple[str, ...] | None = None) -> list[str]:
    return [
        m.organisation_id for m in active_memberships(user) if roles is None or m.role in roles
    ]


def is_org_admin(user: User, org_id: str | None) -> bool:
    m = membership_for(user, org_id)
    return m is not None and m.role == "admin"


def admin_org_ids(user: User) -> list[str]:
    return user_org_ids(user, roles=("admin",))


def log_admin_event(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: str,
    note: str | None = None,
) -> None:
    """Append to the super-admin audit log (guardrail G5). The caller commits."""
    db.add(
        AdminEvent(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            note=note,
        )
    )


def export_allowed(collection: Collection) -> bool:
    """Bulk export (CSV/Markdown/JSON-LD/SKOS/TBX) is off for collections whose
    licence says redistribution is not permitted — content published by
    permission (Samtrafiken, 2026-09-15) stays readable and searchable on the
    site and through the API, but is not handed out as a file. The flag lives
    in the per-collection licence metadata (`licence.redistribution`)."""
    licence = collection.licence or {}
    return licence.get("redistribution") != "not_permitted"


def can_view_collection(user: User | None, collection: Collection) -> bool:
    """public → everyone; org_private → owning-org members and super admins;
    private (personal sandbox) → the creator and super admins."""
    if collection.visibility == "public":
        return True
    if user is None:
        return False
    if user.is_super_admin:
        return True
    if collection.visibility == "org_private":
        return membership_for(user, collection.organisation_id) is not None
    # private: the creator's personal sandbox.
    return bool(collection.created_by) and collection.created_by == user.id


def can_edit_collection(user: User | None, collection: Collection) -> bool:
    """Concept/version writes are policy-driven (edit_policy):

    - 'anyone' → any authenticated account
    - 'org'    → owning-org members (admin|editor) only

    Anonymous users are gone (migration 008): the old 'open' wiki mode is
    migrated to 'anyone' and any remaining 'open' row behaves as 'anyone' —
    an account is always required, because every write becomes immutable
    history that must be attributable.

    Org-owned: an active membership with role admin|editor. Private sandbox:
    the creator. Org-less public (system collection): edit_policy applies.
    Super admins always may; visibility is a separate question answered by
    can_view_collection."""
    if user is None:
        return False
    if user.is_super_admin:
        return True
    if collection.organisation_id:
        m = membership_for(user, collection.organisation_id)
        if m is not None and m.role in ("admin", "editor"):
            return True
    if collection.visibility == "private":
        return bool(collection.created_by) and collection.created_by == user.id
    return collection.edit_policy in ("anyone", "open")


def can_manage_collection(user: User | None, collection: Collection) -> bool:
    """Metadata changes (PATCH): super admin, org admin of the owning org, or
    the creator of a private sandbox. Org-less PUBLIC collections are system
    collections — super admin only (economic-responsibility rule)."""
    if user is None:
        return False
    if user.is_super_admin:
        return True
    if collection.organisation_id:
        return is_org_admin(user, collection.organisation_id)
    if collection.visibility == "private":
        return bool(collection.created_by) and collection.created_by == user.id
    return False


def is_collection_lock_exempt(user: User | None, collection: Collection) -> bool:
    """Locked collections stay writable for owning-org admins and super admins."""
    if user is None:
        return False
    if user.is_super_admin:
        return True
    return is_org_admin(user, collection.organisation_id)


def ensure_write_allowed(
    user: User | None, collection: Collection, *, branch_exempt: bool = False
) -> None:
    """The central write guard for concept/version/relation/import writes:
    401 anonymous → 403 inactive/suspended → 423 archived/locked → 403 rights.

    Iteration 4 refinements:
    - edit_policy 'open' (wiki mode) admits ANONYMOUS writers — the 401 only
      applies to non-open collections. Lock/archive still trump 'open'.
    - branch_exempt=True (mode=branch version-writes): locked collections
      remain writable for ANY authenticated identity — branching is how locked
      content evolves (VISION §4.3). Revise/synthesize/promote stay 423.
    """
    if user is None and collection.edit_policy != "open":
        raise api_error(
            401,
            "login_required",
            "Log in or provide a signature to edit.",
        )
    if user is not None:
        ensure_actor_can_write(user)
    if collection.is_archived:
        raise api_error(
            423,
            "collection_archived",
            "Collection is archived — unarchive it to make changes.",
        )
    # Org-scoped suspension (multi-org, 2026-07): a suspended org blocks
    # writes into ITS collections — never the actor's writes elsewhere.
    if (
        collection.organisation is not None
        and collection.organisation.is_suspended
        and not (user is not None and user.is_super_admin)
    ):
        raise api_error(403, "org_suspended", "Organisation is suspended.")
    if collection.is_locked:
        if branch_exempt and user is not None:
            return  # any authed identity may branch locked content
        if not is_collection_lock_exempt(user, collection):
            raise api_error(
                423,
                "collection_locked",
                "Collection is locked — only the owning organisation's admins "
                "or super admins may edit.",
            )
    if not can_edit_collection(user, collection):
        owner = collection.organisation.name if collection.organisation else "en organisation"
        raise api_error(
            403,
            "collection_edit_forbidden",
            f"Collection is owned by {owner} — membership (editor or admin) "
            "is required to edit in it.",
            owner=owner,
        )


def visible_collection_criterion(user: User | None) -> ColumnElement[bool]:
    """SQLAlchemy filter matching can_view_collection, for list queries.
    The user's org ids are resolved python-side (a user's membership count is
    tiny) and inlined as an IN clause."""
    if user is not None and user.is_super_admin:
        return true()
    clauses: list[ColumnElement[bool]] = [Collection.visibility == "public"]
    if user is not None:
        # private sandboxes: the creator only.
        clauses.append((Collection.visibility == "private") & (Collection.created_by == user.id))
        org_ids = user_org_ids(user)
        if org_ids:
            clauses.append(
                (Collection.visibility == "org_private") & Collection.organisation_id.in_(org_ids)
            )
    return or_(*clauses)
