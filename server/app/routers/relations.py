"""Concept-relation endpoints.

Iteration 3: relation writes run through the same central guard as concept and
version writes (deps.ensure_write_allowed) — for BOTH endpoint collections,
so a locked/archived collection cannot be modified from the other side of
the relation either.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import can_view_collection, current_user, ensure_write_allowed
from ..errors import api_error
from ..models import RELATION_TYPES, Concept, ConceptRelation, User

router = APIRouter(prefix="/relations", tags=["relations"])


def _get_visible_concept(db: Session, concept_id: str, user: User | None) -> Concept:
    concept = db.get(Concept, concept_id)
    if concept is None or not can_view_collection(user, concept.collection):
        raise api_error(
            404, "concept_not_found", f"Concept {concept_id} not found", concept_id=concept_id
        )
    return concept


@router.post("", status_code=201)
def create_relation(
    payload: schemas.RelationCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, str]:
    if payload.relation_type not in RELATION_TYPES:
        raise api_error(
            422,
            "unknown_relation_type",
            f"Unknown relation type: allowed {RELATION_TYPES}",
            relation_type=payload.relation_type,
            allowed=list(RELATION_TYPES),
        )
    concepts = [
        _get_visible_concept(db, concept_id, user)
        for concept_id in (payload.from_concept_id, payload.to_concept_id)
    ]
    for concept in concepts:
        ensure_write_allowed(user, concept.collection)
    relation = ConceptRelation(
        relation_type=payload.relation_type,
        from_concept_id=payload.from_concept_id,
        to_concept_id=payload.to_concept_id,
        note=payload.note,
        created_by=user.id if user else None,
    )
    db.add(relation)
    db.commit()
    return {"id": relation.id}


@router.delete("/{relation_id}", status_code=204)
def delete_relation(
    relation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> None:
    relation = db.get(ConceptRelation, relation_id)
    if relation is None:
        raise api_error(404, "relation_not_found", "Relation not found")
    for concept_id in (relation.from_concept_id, relation.to_concept_id):
        concept = db.get(Concept, concept_id)
        if concept is not None:
            ensure_write_allowed(user, concept.collection)
    db.delete(relation)
    db.commit()
