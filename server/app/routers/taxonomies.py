"""Taxonomies — curated controlled vocabularies (plan NG_TAXONOMIES, 2026-07-11).

Two scopes, one machinery:
- 'global': the cross-collection categories, the global search axis. Curated
  by SUPER ADMINS and deliberately mutable over time — the vocabulary follows
  the corpus to keep global search simple.
- 'collection': a collection's own structure (the source standard's Parts,
  subject areas). Curated by the collection's managers.

Assignments live on the CONCEPT (not the version) with an audit trail —
recategorisation is curation work and never mints new text versions.
min_per_concept is SOFT (UI/import guidance); max_per_concept is HARD when
set (parts use min=max=1).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from .. import schemas
from ..db import get_db
from ..deps import (
    can_edit_collection,
    can_manage_collection,
    can_view_collection,
    current_user,
    ensure_actor_can_write,
    is_collection_lock_exempt,
)
from ..errors import api_error
from ..models import (
    Collection,
    Concept,
    ConceptTaxonomyValue,
    Taxonomy,
    TaxonomyValue,
    User,
)

router = APIRouter(tags=["taxonomies"])


class TaxonomyCreateIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    scope: str = Field(pattern="^(global|collection)$")
    collection_id: str | None = None
    min_per_concept: int = Field(default=0, ge=0)
    max_per_concept: int | None = Field(default=None, ge=1)


class TaxonomyPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    min_per_concept: int | None = Field(default=None, ge=0)
    max_per_concept: int | None = Field(default=None, ge=1)


class ValueIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    position: int | None = None


class AssignIn(BaseModel):
    value_ids: list[str] = Field(default_factory=list)


def taxonomy_out(taxonomy: Taxonomy) -> schemas.TaxonomyOut:
    return schemas.TaxonomyOut(
        id=taxonomy.id,
        slug=taxonomy.slug,
        name=taxonomy.name,
        description=taxonomy.description,
        scope=taxonomy.scope,
        collection_id=taxonomy.collection_id,
        min_per_concept=taxonomy.min_per_concept,
        max_per_concept=taxonomy.max_per_concept,
        values=[
            schemas.TaxonomyValueOut(
                id=v.id, name=v.name, name_en=v.name_en, position=v.position
            )
            for v in taxonomy.values
        ],
    )


def _require_curator(
    db: Session, user: User | None, taxonomy_scope: str, collection: Collection | None
) -> User:
    if user is None:
        raise api_error(401, "login_required", "Login required.")
    ensure_actor_can_write(user)
    if taxonomy_scope == "global":
        if not user.is_super_admin:
            raise api_error(
                403,
                "taxonomy_global_curators_only",
                "Global categories are curated by Kollepedia's super administrators.",
            )
        return user
    if collection is None or not can_manage_collection(user, collection):
        raise api_error(
            403,
            "taxonomy_collection_curators_only",
            "The collection's taxonomies are curated by its administrators.",
        )
    return user


@router.get("/taxonomies", response_model=list[schemas.TaxonomyOut])
def list_taxonomies(
    collection: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.TaxonomyOut]:
    """Global taxonomies + (optionally) one collection's own."""
    query = db.query(Taxonomy).options(joinedload(Taxonomy.values))
    if collection:
        coll = db.query(Collection).filter(Collection.slug == collection).first()
        if coll is None or not can_view_collection(user, coll):
            raise api_error(
                404, "collection_not_found", "Collection not found", slug=collection
            )
        query = query.filter(
            (Taxonomy.scope == "global") | (Taxonomy.collection_id == coll.id)
        )
    else:
        query = query.filter(Taxonomy.scope == "global")
    return [taxonomy_out(t) for t in query.order_by(Taxonomy.created_at.asc()).all()]


@router.post("/taxonomies", response_model=schemas.TaxonomyOut, status_code=201)
def create_taxonomy(
    payload: TaxonomyCreateIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.TaxonomyOut:
    collection: Collection | None = None
    if payload.scope == "collection":
        if not payload.collection_id:
            raise api_error(
                422,
                "taxonomy_collection_id_required",
                "collection_id is required for collection-scoped taxonomies.",
            )
        collection = db.get(Collection, payload.collection_id)
        if collection is None:
            raise api_error(
                404,
                "collection_not_found",
                "Collection not found",
                collection_id=payload.collection_id,
            )
    _require_curator(db, user, payload.scope, collection)
    exists = (
        db.query(Taxonomy)
        .filter(
            Taxonomy.slug == payload.slug,
            Taxonomy.collection_id == (collection.id if collection else None),
        )
        .first()
    )
    if exists is not None:
        raise api_error(
            409, "taxonomy_already_exists", "Taxonomy already exists.", slug=payload.slug
        )
    taxonomy = Taxonomy(
        slug=payload.slug.strip().lower(),
        name=payload.name.strip(),
        description=payload.description,
        scope=payload.scope,
        collection_id=collection.id if collection else None,
        min_per_concept=payload.min_per_concept,
        max_per_concept=payload.max_per_concept,
    )
    db.add(taxonomy)
    db.commit()
    return taxonomy_out(taxonomy)


def _get_taxonomy(db: Session, taxonomy_id: str) -> Taxonomy:
    taxonomy = db.get(Taxonomy, taxonomy_id)
    if taxonomy is None:
        raise api_error(
            404, "taxonomy_not_found", "Taxonomy not found", taxonomy_id=taxonomy_id
        )
    return taxonomy


def _taxonomy_collection(db: Session, taxonomy: Taxonomy) -> Collection | None:
    return db.get(Collection, taxonomy.collection_id) if taxonomy.collection_id else None


@router.patch("/taxonomies/{taxonomy_id}", response_model=schemas.TaxonomyOut)
def patch_taxonomy(
    taxonomy_id: str,
    payload: TaxonomyPatchIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.TaxonomyOut:
    taxonomy = _get_taxonomy(db, taxonomy_id)
    _require_curator(db, user, taxonomy.scope, _taxonomy_collection(db, taxonomy))
    if payload.name is not None:
        taxonomy.name = payload.name.strip()
    if payload.description is not None:
        taxonomy.description = payload.description
    if payload.min_per_concept is not None:
        taxonomy.min_per_concept = payload.min_per_concept
    if payload.max_per_concept is not None:
        taxonomy.max_per_concept = payload.max_per_concept
    db.commit()
    return taxonomy_out(taxonomy)


@router.post(
    "/taxonomies/{taxonomy_id}/values",
    response_model=schemas.TaxonomyValueOut,
    status_code=201,
)
def create_value(
    taxonomy_id: str,
    payload: ValueIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.TaxonomyValueOut:
    taxonomy = _get_taxonomy(db, taxonomy_id)
    _require_curator(db, user, taxonomy.scope, _taxonomy_collection(db, taxonomy))
    name = payload.name.strip()
    if any(v.name == name for v in taxonomy.values):
        raise api_error(
            409,
            "taxonomy_value_already_exists",
            "The value already exists in the taxonomy.",
            name=name,
        )
    position = (
        payload.position
        if payload.position is not None
        else (max((v.position for v in taxonomy.values), default=-1) + 1)
    )
    value = TaxonomyValue(
        taxonomy_id=taxonomy.id,
        name=name,
        name_en=payload.name_en.strip() if payload.name_en else None,
        position=position,
    )
    db.add(value)
    db.commit()
    return schemas.TaxonomyValueOut(
        id=value.id, name=value.name, name_en=value.name_en, position=value.position
    )


@router.patch("/taxonomy-values/{value_id}", response_model=schemas.TaxonomyValueOut)
def patch_value(
    value_id: str,
    payload: ValueIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.TaxonomyValueOut:
    value = db.get(TaxonomyValue, value_id)
    if value is None:
        raise api_error(
            404, "taxonomy_value_not_found", "Value not found", value_id=value_id
        )
    taxonomy = value.taxonomy
    _require_curator(db, user, taxonomy.scope, _taxonomy_collection(db, taxonomy))
    name = payload.name.strip()
    if name != value.name and any(v.name == name for v in taxonomy.values):
        raise api_error(
            409,
            "taxonomy_value_already_exists",
            "The value already exists in the taxonomy.",
            name=name,
        )
    value.name = name
    if payload.name_en is not None:
        value.name_en = payload.name_en.strip() or None
    if payload.position is not None:
        value.position = payload.position
    db.commit()
    return schemas.TaxonomyValueOut(
        id=value.id, name=value.name, name_en=value.name_en, position=value.position
    )


@router.delete("/taxonomy-values/{value_id}", status_code=204)
def delete_value(
    value_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> None:
    value = db.get(TaxonomyValue, value_id)
    if value is None:
        raise api_error(
            404, "taxonomy_value_not_found", "Value not found", value_id=value_id
        )
    taxonomy = value.taxonomy
    _require_curator(db, user, taxonomy.scope, _taxonomy_collection(db, taxonomy))
    db.query(ConceptTaxonomyValue).filter(ConceptTaxonomyValue.value_id == value.id).delete()
    db.delete(value)
    db.commit()


@router.put(
    "/concepts/{concept_id}/taxonomies/{taxonomy_id}",
    response_model=list[schemas.TaxonomyValueOut],
)
def assign_values(
    concept_id: str,
    taxonomy_id: str,
    payload: AssignIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.TaxonomyValueOut]:
    """Replace the concept's assignment set for ONE taxonomy."""
    concept = db.get(Concept, concept_id)
    if concept is None or not can_view_collection(user, concept.collection):
        raise api_error(
            404, "concept_not_found", "Concept not found", concept_id=concept_id
        )
    if user is None:
        raise api_error(401, "login_required", "Login required.")
    ensure_actor_can_write(user)
    if not can_edit_collection(user, concept.collection):
        raise api_error(
            403,
            "collection_edit_forbidden",
            "You lack editing rights in this collection.",
        )
    if concept.collection.is_archived:
        raise api_error(423, "collection_archived", "The collection is archived.")
    # Locked collections: same exemption rule as content writes (Bengt #1).
    if concept.collection.is_locked and not is_collection_lock_exempt(
        user, concept.collection
    ):
        raise api_error(423, "collection_locked", "The collection is locked.")
    taxonomy = _get_taxonomy(db, taxonomy_id)
    if taxonomy.scope == "collection" and taxonomy.collection_id != concept.collection_id:
        raise api_error(
            422,
            "taxonomy_collection_mismatch",
            "The taxonomy belongs to a different collection.",
        )
    valid_ids = {v.id: v for v in taxonomy.values}
    unique_ids = list(dict.fromkeys(payload.value_ids))
    unknown = [v for v in unique_ids if v not in valid_ids]
    if unknown:
        raise api_error(
            422,
            "taxonomy_value_unknown",
            "Unknown value for the taxonomy.",
            value_ids=unknown,
        )
    # max is HARD when set (parts use max=1); min stays soft EXCEPT when
    # min == max (exact cardinality, e.g. parts) — then the floor is hard too
    # (Bengt #5). An empty set is always allowed (unassigning).
    if taxonomy.max_per_concept is not None and len(unique_ids) > taxonomy.max_per_concept:
        raise api_error(
            422,
            "taxonomy_max_values_exceeded",
            f"The taxonomy allows at most {taxonomy.max_per_concept} value(s) per concept.",
            max=taxonomy.max_per_concept,
        )
    if (
        unique_ids
        and taxonomy.max_per_concept is not None
        and taxonomy.min_per_concept == taxonomy.max_per_concept
        and len(unique_ids) < taxonomy.min_per_concept
    ):
        raise api_error(
            422,
            "taxonomy_exact_values_required",
            f"The taxonomy requires exactly {taxonomy.min_per_concept} value(s) per concept.",
            exact=taxonomy.min_per_concept,
        )
    db.query(ConceptTaxonomyValue).filter(
        ConceptTaxonomyValue.concept_id == concept.id,
        ConceptTaxonomyValue.value_id.in_(list(valid_ids.keys())),
    ).delete(synchronize_session=False)
    for value_id in unique_ids:
        db.add(
            ConceptTaxonomyValue(
                concept_id=concept.id, value_id=value_id, added_by=user.id
            )
        )
    db.commit()
    return [
        schemas.TaxonomyValueOut(
            id=valid_ids[v].id,
            name=valid_ids[v].name,
            name_en=valid_ids[v].name_en,
            position=valid_ids[v].position,
        )
        for v in unique_ids
    ]
