"""Authors — the public author surface and the admin outreach workbench.

Author and user are the same entity: an "author" is any user with ≥1 authored
version (versions.created_by) or ≥1 section 'author' annotation (linked via
value.user_id, written by migration 003). Unactivated authors
(password_hash NULL) are ACTIVATED through the existing claim-on-register
rule in routers/auth.py — nothing here duplicates that mechanism.

Outreach is strictly manual (product rule: opt-out, NO automatic
contact ever). The API only bookkeeps the admin's own manual workflow:
outreach_status NULL = not contacted, 'contacted', 'opted_out'. Opt-out is
sacred: it can never be flipped to 'contacted', and clearing it requires an
explicit confirmation flag.
"""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require_user, visible_collection_criterion
from ..errors import api_error
from ..models import (
    ActivationToken,
    Annotation,
    Branch,
    Collection,
    Concept,
    User,
    Version,
    utcnow,
)

router = APIRouter(tags=["authors"])


# --------------------------------------------------------------------------
# Schemas (module-local, like orgs.py)
# --------------------------------------------------------------------------


class AuthorCollectionOut(BaseModel):
    slug: str
    name: str


class AuthorMembershipOut(BaseModel):
    """Public membership row (beslut 4): org + role + kind, never email.
    Hidden (is_public=False) and ended memberships are only serialised for
    super-admin viewers — the flags let the admin UI mark them as such."""

    org_slug: str
    org_name: str
    role: str
    kind: str = "member"
    is_public: bool = True
    ended_at: datetime | None = None


class AuthorOut(BaseModel):
    id: str
    handle: str
    display_name: str
    affiliation: str | None = None
    web_url: str | None = None
    bio: str | None = None
    activated: bool = False
    is_active: bool = True
    version_count: int = 0
    section_count: int = 0
    concept_count: int = 0
    collections: list[AuthorCollectionOut]
    memberships: list[AuthorMembershipOut] = []


class AuthorConceptOut(BaseModel):
    id: str
    canonical_form: str
    collection_slug: str
    collection_name: str


class AuthorDetailOut(AuthorOut):
    concepts: list[AuthorConceptOut]


class OutreachRowOut(AuthorOut):
    outreach_status: str | None = None
    outreach_note: str | None = None
    outreach_updated_at: datetime | None = None


class OutreachPatchIn(BaseModel):
    # Explicit null = "not contacted". Only these two values are ever stored.
    status: str | None
    note: str | None = None
    confirm_clear_opt_out: bool = False


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


class _Stats:
    __slots__ = ("version_count", "section_count", "concept_ids", "collections")

    def __init__(self) -> None:
        self.version_count = 0
        self.section_count = 0
        self.concept_ids: set[str] = set()
        self.collections: dict[str, str] = {}  # slug -> name


def _collect_stats(db: Session, viewer: User | None) -> dict[str, _Stats]:
    """Per-user authorship stats, restricted to collections the viewer may see
    (org_private work is not disclosed to outsiders — super admins see all)."""
    visible = visible_collection_criterion(viewer)
    stats: dict[str, _Stats] = {}

    def bucket(user_id: str) -> _Stats:
        if user_id not in stats:
            stats[user_id] = _Stats()
        return stats[user_id]

    version_rows = (
        db.query(
            Version.created_by,
            Version.concept_id,
            Collection.slug,
            Collection.name,
            func.count(Version.id),
        )
        .join(Concept, Concept.id == Version.concept_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(Version.created_by.isnot(None), visible)
        .group_by(Version.created_by, Version.concept_id)
        .all()
    )
    for user_id, concept_id, slug, name, count in version_rows:
        entry = bucket(user_id)
        entry.version_count += count
        entry.concept_ids.add(concept_id)
        entry.collections[slug] = name

    annotation_user = Annotation.value["user_id"].as_string()
    annotation_rows = (
        db.query(
            annotation_user,
            Version.concept_id,
            Collection.slug,
            Collection.name,
            func.count(Annotation.id),
        )
        .join(Version, Version.id == Annotation.version_id)
        .join(Concept, Concept.id == Version.concept_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(Annotation.attr_type == "author", annotation_user.isnot(None), visible)
        .group_by(annotation_user, Version.concept_id)
        .all()
    )
    for user_id, concept_id, slug, name, count in annotation_rows:
        entry = bucket(user_id)
        entry.section_count += count
        entry.concept_ids.add(concept_id)
        entry.collections[slug] = name

    return stats


def _author_memberships(user: User, viewer: User | None) -> list[AuthorMembershipOut]:
    """Active PUBLIC memberships for everyone; super admins additionally see
    hidden and ended ones (flagged, for the moderation surface)."""
    is_super = viewer is not None and viewer.is_super_admin
    rows = [
        AuthorMembershipOut(
            org_slug=m.organisation.slug,
            org_name=m.organisation.name,
            role=m.role,
            kind=m.kind,
            is_public=m.is_public,
            ended_at=m.ended_at,
        )
        for m in user.memberships
        if is_super or (m.is_public and m.ended_at is None)
    ]
    rows.sort(key=lambda m: (m.ended_at is not None, m.org_name.lower()))
    return rows


def _author_out(user: User, entry: _Stats, viewer: User | None = None) -> AuthorOut:
    return AuthorOut(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        affiliation=user.affiliation,
        web_url=user.web_url,
        bio=user.bio,
        activated=user.password_hash is not None,
        is_active=user.is_active,
        version_count=entry.version_count,
        section_count=entry.section_count,
        concept_count=len(entry.concept_ids),
        collections=[
            AuthorCollectionOut(slug=slug, name=name)
            for slug, name in sorted(entry.collections.items(), key=lambda kv: kv[1])
        ],
        memberships=_author_memberships(user, viewer),
    )


def _author_concepts(db: Session, entry: _Stats, limit: int = 100) -> list[AuthorConceptOut]:
    if not entry.concept_ids:
        return []
    rows = (
        db.query(Concept.id, Version.canonical_form, Collection.slug, Collection.name)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(Concept.id.in_(entry.concept_ids))
        .order_by(Version.canonical_form.asc())
        .limit(limit)
        .all()
    )
    return [
        AuthorConceptOut(
            id=concept_id, canonical_form=form, collection_slug=slug, collection_name=name
        )
        for concept_id, form, slug, name in rows
    ]


# --------------------------------------------------------------------------
# Public author surface
# --------------------------------------------------------------------------


@router.get("/authors", response_model=list[AuthorOut])
def list_authors(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[AuthorOut]:
    stats = _collect_stats(db, user)
    if not stats:
        return []
    query = db.query(User).filter(User.id.in_(stats.keys()))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.handle.ilike(like),
                User.display_name.ilike(like),
                User.affiliation.ilike(like),
            )
        )
    authors = query.order_by(User.display_name.asc()).limit(limit).all()
    return [_author_out(a, stats[a.id], user) for a in authors]


@router.get("/authors/{handle}", response_model=AuthorDetailOut)
def get_author(
    handle: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> AuthorDetailOut:
    target = db.query(User).filter(User.handle == handle.strip().lower()).first()
    if target is None:
        raise api_error(404, "author_not_found", "Author not found.", handle=handle)
    stats = _collect_stats(db, user)
    entry = stats.get(target.id)
    if entry is None:
        # Users without any (visible) authorship are not part of the public
        # author surface — do not disclose them.
        raise api_error(404, "author_not_found", "Author not found.", handle=handle)
    base = _author_out(target, entry, user)
    return AuthorDetailOut(
        **base.model_dump(), concepts=[c.model_dump() for c in _author_concepts(db, entry)]
    )


# --------------------------------------------------------------------------
# Admin outreach workbench (super admin only)
# --------------------------------------------------------------------------


def require_super_admin(user: User = Depends(require_user)) -> User:
    if not user.is_super_admin:
        raise api_error(
            403,
            "super_admin_required",
            "Only super administrators can access the outreach view.",
        )
    return user


def _outreach_row(user: User, entry: _Stats) -> OutreachRowOut:
    base = _author_out(user, entry)
    return OutreachRowOut(
        **base.model_dump(),
        outreach_status=user.outreach_status,
        outreach_note=user.outreach_note,
        outreach_updated_at=user.outreach_updated_at,
    )


@router.get("/admin/outreach", response_model=list[OutreachRowOut])
def list_outreach(
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> list[OutreachRowOut]:
    stats = _collect_stats(db, admin)  # super admin → all collections visible
    if not stats:
        return []
    authors = (
        db.query(User).filter(User.id.in_(stats.keys())).order_by(User.display_name.asc()).all()
    )
    return [_outreach_row(a, stats[a.id]) for a in authors]


@router.patch("/admin/outreach/{user_id}", response_model=OutreachRowOut)
def patch_outreach(
    user_id: str,
    payload: OutreachPatchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> OutreachRowOut:
    if payload.status not in (None, "contacted", "opted_out"):
        raise api_error(
            422,
            "invalid_outreach_status",
            "Invalid status; allowed values: contacted, opted_out or null.",
            status=payload.status,
            allowed="contacted, opted_out, null",
        )
    target = db.get(User, user_id)
    if target is None:
        raise api_error(404, "user_not_found", "User not found.", user_id=user_id)

    # Opt-out is sacred: never flip to 'contacted'; clearing needs explicit intent.
    if target.outreach_status == "opted_out":
        if payload.status == "contacted":
            raise api_error(
                409, "author_opted_out", "The author has opted out; do not contact again."
            )
        if payload.status is None and not payload.confirm_clear_opt_out:
            raise api_error(
                409,
                "opt_out_clear_requires_confirmation",
                "The author has opted out of contact. Clearing the flag "
                "requires explicit confirmation (confirm_clear_opt_out).",
            )

    target.outreach_status = payload.status
    if "note" in payload.model_fields_set:
        target.outreach_note = payload.note
    target.outreach_updated_at = utcnow()
    db.commit()

    stats = _collect_stats(db, admin)
    return _outreach_row(target, stats.get(target.id, _Stats()))


# Long-lived on purpose: outreach mail is manual and authors answer slowly.
ACTIVATION_TOKEN_TTL = timedelta(days=30)


class ActivationLinkOut(BaseModel):
    url: str
    expires_at: datetime


@router.post(
    "/admin/outreach/{user_id}/activation-link",
    response_model=ActivationLinkOut,
    status_code=201,
)
def mint_activation_link(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
) -> ActivationLinkOut:
    """Mint a personal one-time activation link for an unclaimed author.
    Claiming with the link is verified by construction and skips manual
    review; a claim without it stays review-gated (routers/auth.py). The
    admin sends the link manually — outreach never mails automatically."""
    # Local import — auth.py imports nothing from this module, no cycle risk
    # the other way either, but the routers otherwise only depend downwards.
    from .auth import hash_token

    target = db.get(User, user_id)
    if target is None:
        raise api_error(404, "user_not_found", "User not found.", user_id=user_id)
    if not target.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    if target.password_hash is not None:
        raise api_error(
            409,
            "author_already_activated",
            "The author has already activated their account.",
        )
    if target.outreach_status == "opted_out":
        raise api_error(409, "author_opted_out", "The author has opted out; do not contact again.")

    raw = secrets.token_urlsafe(32)
    expires_at = utcnow() + ACTIVATION_TOKEN_TTL
    db.add(ActivationToken(user_id=target.id, token_hash=hash_token(raw), expires_at=expires_at))
    db.commit()
    return ActivationLinkOut(
        url=f"/activate?handle={target.handle}&token={raw}", expires_at=expires_at
    )
