"""ORM → schema serializers shared across routers."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import schemas
from .deps import can_edit_collection, can_manage_collection, export_allowed
from .models import Collection, Concept, User, Version


def collection_out(
    collection: Collection, concept_count: int = 0, user: User | None = None
) -> schemas.CollectionOut:
    org = collection.organisation
    return schemas.CollectionOut(
        id=collection.id,
        slug=collection.slug,
        name=collection.name,
        description=collection.description,
        year=collection.year,
        authoritative=collection.authoritative,
        licence=collection.licence,
        concept_count=concept_count,
        visibility=collection.visibility,
        organisation=(
            schemas.CollectionOrgOut(id=org.id, slug=org.slug, name=org.name) if org else None
        ),
        created_by=collection.creator.handle if collection.creator else None,
        editable=can_manage_collection(user, collection),
        # can_write drives the frontend's write-tool visibility (UI-gating
        # 2026-07-15): show edit/revise/relations only to those the server
        # would actually let write. Mirrors ensure_write_allowed's edit check.
        can_write=can_edit_collection(user, collection),
        is_locked=collection.is_locked,
        is_archived=collection.is_archived,
        export_allowed=export_allowed(collection),
        edit_policy=collection.edit_policy,
        source_url=collection.source_url,
        archive_url=collection.archive_url,
        credits=collection.credits,
        sources=collection.sources,
        locales=collection.locales,
    )


def user_out(user: User | None) -> schemas.UserOut | None:
    if user is None:
        return None
    return schemas.UserOut(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        affiliation=user.affiliation,
    )


def version_out(
    version: Version,
    users: dict[str, User] | None = None,
    include_annotations: bool = True,
) -> schemas.VersionOut:
    creator = None
    if version.created_by:
        creator = (users or {}).get(version.created_by) or version.creator
    return schemas.VersionOut(
        id=version.id,
        concept_id=version.concept_id,
        branch_id=version.branch_id,
        language=version.language,
        canonical_form=version.canonical_form,
        definition_md=version.definition_md,
        status=version.status,
        tags=list(version.tags or []),
        note=version.note,
        provenance=dict(version.provenance or {}),
        created_at=version.created_at,
        created_by=user_out(creator),
        annotations=[
            schemas.AnnotationOut(
                id=a.id,
                attr_type=a.attr_type,
                start=a.start,
                end=a.end,
                quote=a.quote,
                value=dict(a.value or {}),
                provenance=dict(a.provenance or {}),
            )
            for a in (version.annotations if include_annotations else [])
        ],
        endorsements=[
            schemas.EndorsementOut(
                id=e.id,
                body=e.body,
                organisation=(
                    schemas.EndorsementOrgOut(
                        id=e.organisation.id,
                        slug=e.organisation.slug,
                        name=e.organisation.name,
                    )
                    if e.organisation
                    else None
                ),
                note=e.note,
                created_at=e.created_at,
                withdrawn_at=e.withdrawn_at,
                withdrawal_note=e.withdrawal_note,
            )
            for e in version.endorsements
        ],
    )


def concept_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(Concept.collection_id, func.count(Concept.id))
        .group_by(Concept.collection_id)
        .all()
    )
    return {collection_id: count for collection_id, count in rows}
