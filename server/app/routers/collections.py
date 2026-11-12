"""Collection endpoints — reads with visibility filtering, plus management
(POST/PATCH) with org-aware authorisation (iteration 2)."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import (
    can_manage_collection,
    can_view_collection,
    current_user,
    ensure_actor_can_write,
    is_org_admin,
    require_user,
    visible_collection_criterion,
)
from ..errors import api_error
from ..models import Annotation, Collection, Concept, Organisation, User, Version
from ..serialize import collection_out, concept_counts
from .orgs import SLUG_RE

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreateIn(BaseModel):
    slug: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=schemas.DESCRIPTION_MAX)
    year: int | None = None
    licence: dict[str, Any] | None = None
    organisation_id: str | None = None
    visibility: Literal["public", "org_private", "private"] = "public"
    # Iteration 4: defaults to 'org' for org-owned collections, 'anyone' otherwise.
    edit_policy: Literal["org", "anyone"] | None = None


class CollectionPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=schemas.DESCRIPTION_MAX)
    year: int | None = None
    licence: dict[str, Any] | None = None
    organisation_id: str | None = None
    visibility: Literal["public", "org_private", "private"] | None = None
    authoritative: bool | None = None
    # Iteration 3: lock/archive toggles (manage rights; PATCH stays open on an
    # archived collection — it is the only way to unarchive).
    is_locked: bool | None = None
    is_archived: bool | None = None
    # Iteration 4: editing policy (manage rights, like every other PATCH field).
    edit_policy: Literal["org", "anyone"] | None = None
    # Migration 007 rich metadata: credits + provenance URLs are editable with
    # manage rights. sources/locales stay import-only (not accepted here) —
    # unknown fields are ignored by pydantic, so sending them changes nothing.
    credits: str | None = None
    source_url: str | None = None
    archive_url: str | None = None


def _require_org_assignable(db: Session, user: User, organisation_id: str) -> None:
    """Assigning a collection to an org requires ADMIN of an approved,
    non-suspended org (economic responsibility) — or super admin."""
    org = db.get(Organisation, organisation_id)
    if org is None:
        raise api_error(404, "org_not_found", "Organisation not found")
    if user.is_super_admin:
        return
    if not is_org_admin(user, org.id):
        raise api_error(
            403,
            "org_admin_required",
            "Collections are owned by an organisation and managed by its "
            "administrators — you must be an admin of the organisation.",
        )
    if not org.is_approved:
        raise api_error(
            403,
            "org_not_approved",
            "The organisation is not approved yet — collections require an approved organisation.",
        )
    if org.is_suspended:
        raise api_error(403, "org_suspended", "The organisation is suspended.")


def _validate_visibility_org(*, visibility: str, organisation_id: str | None, user: User) -> None:
    """The funnel rules (beslut 2): org-less collections are PRIVATE sandboxes
    (except super-admin system collections); private collections are personal
    — they cannot belong to an organisation."""
    if visibility == "private" and organisation_id:
        raise api_error(
            422,
            "private_collection_no_org",
            "A private sandbox is personal — it cannot be owned by an organisation.",
        )
    if visibility != "private" and not organisation_id and not user.is_super_admin:
        raise api_error(
            422,
            "collection_org_required",
            "Publishing or collaborating on a collection requires an owning "
            "organisation where you are an admin. Without an organisation you "
            "can create a private sandbox (visible only to you).",
        )


@router.get("", response_model=list[schemas.CollectionOut])
def list_collections(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.CollectionOut]:
    counts = concept_counts(db)
    query = db.query(Collection).filter(visible_collection_criterion(user))
    if not include_archived:
        # Archived collections are hidden from the list (direct GET still works).
        query = query.filter(Collection.is_archived.is_(False))
    collections = query.order_by(Collection.year.asc().nulls_last()).all()
    return [collection_out(c, counts.get(c.id, 0), user=user) for c in collections]


def _contributors_for(db: Session, collection: Collection) -> list[schemas.ContributorOut]:
    """Paket B: the collection's living author list — the equivalent of the
    old Ordbok page's publication credit, computed instead of curated. Union
    of (a) version authorship (`Version.created_by`) and (b) per-section
    author annotations (`value.user_id`), for concepts in this collection.
    'Redaktörerna' is an editorial credit, not a person — it is filtered out
    here but still shows in term-level bylines where it is the only
    attribution (beslut 1, 2026-07-12)."""
    version_counts: dict[str, int] = dict(
        db.query(Version.created_by, func.count(Version.id))
        .join(Concept, Concept.id == Version.concept_id)
        .filter(Concept.collection_id == collection.id, Version.created_by.isnot(None))
        .group_by(Version.created_by)
        .all()
    )
    annotation_user = Annotation.value["user_id"].as_string()
    section_counts: dict[str, int] = dict(
        db.query(annotation_user, func.count(Annotation.id))
        .join(Version, Version.id == Annotation.version_id)
        .join(Concept, Concept.id == Version.concept_id)
        .filter(
            Concept.collection_id == collection.id,
            Annotation.attr_type == "author",
            annotation_user.isnot(None),
        )
        .group_by(annotation_user)
        .all()
    )
    user_ids = set(version_counts) | set(section_counts)
    if not user_ids:
        return []
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    rows = [
        schemas.ContributorOut(
            handle=u.handle,
            display_name=u.display_name,
            affiliation=u.affiliation,
            activated=u.password_hash is not None,
            version_count=version_counts.get(u.id, 0),
            section_count=section_counts.get(u.id, 0),
        )
        for u in users
        if u.display_name != "Redaktörerna"
    ]
    rows.sort(key=lambda r: r.display_name.lower())
    return rows


@router.get("/{slug}", response_model=schemas.CollectionOut)
def get_collection(
    slug: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.CollectionOut:
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if collection is None or not can_view_collection(user, collection):
        raise api_error(404, "collection_not_found", "Collection not found")
    counts = concept_counts(db)
    out = collection_out(collection, counts.get(collection.id, 0), user=user)
    out.contributors = _contributors_for(db, collection)
    return out


@router.post("", response_model=schemas.CollectionOut, status_code=201)
def create_collection(
    payload: CollectionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.CollectionOut:
    ensure_actor_can_write(user)
    slug = payload.slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise api_error(
            422,
            "invalid_slug",
            "Invalid slug — use lowercase letters a–z, digits and hyphens.",
        )
    if db.query(Collection).filter(Collection.slug == slug).first():
        raise api_error(
            409, "slug_taken", "A collection with that slug already exists — pick another."
        )
    _validate_visibility_org(
        visibility=payload.visibility, organisation_id=payload.organisation_id, user=user
    )
    if payload.organisation_id:
        _require_org_assignable(db, user, payload.organisation_id)
    collection = Collection(
        slug=slug,
        name=payload.name.strip(),
        description=payload.description,
        year=payload.year,
        licence=payload.licence,
        organisation_id=payload.organisation_id,
        visibility=payload.visibility,
        edit_policy=payload.edit_policy or ("org" if payload.organisation_id else "anyone"),
        created_by=user.id,
    )
    db.add(collection)
    db.commit()
    return collection_out(collection, 0, user=user)


@router.patch("/{slug}", response_model=schemas.CollectionOut)
def patch_collection(
    slug: str,
    payload: CollectionPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.CollectionOut:
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if collection is None or not can_view_collection(user, collection):
        raise api_error(404, "collection_not_found", "Collection not found")
    ensure_actor_can_write(user)
    if not can_manage_collection(user, collection):
        raise api_error(
            403,
            "collection_manage_forbidden",
            "Only the organisation's administrators, the collection's creator "
            "or super administrators can modify the collection.",
        )
    # Org-scoped suspension covers collection METADATA too — a suspended
    # org's admins cannot manage its collections (super admins can).
    if (
        collection.organisation is not None
        and collection.organisation.is_suspended
        and not user.is_super_admin
    ):
        raise api_error(403, "org_suspended", "The organisation is suspended.")
    data = payload.model_dump(exclude_unset=True)
    if "authoritative" in data and not user.is_super_admin:
        raise api_error(
            403,
            "authoritative_super_admin_only",
            "Only super administrators can change the authoritative flag.",
        )
    # The funnel (beslut 2): validate the RESULTING visibility/org pair —
    # taking a sandbox public requires assigning an org (where the actor is
    # admin) in the same PATCH or before it.
    resulting_visibility = data.get("visibility", collection.visibility)
    resulting_org = (
        data["organisation_id"] if "organisation_id" in data else collection.organisation_id
    )
    _validate_visibility_org(
        visibility=resulting_visibility, organisation_id=resulting_org, user=user
    )
    new_org = data.get("organisation_id")
    if new_org and new_org != collection.organisation_id:
        _require_org_assignable(db, user, new_org)
    for key, value in data.items():
        setattr(collection, key, value)
    db.commit()
    counts = concept_counts(db)
    return collection_out(collection, counts.get(collection.id, 0), user=user)
