"""Stats and misc endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import current_user, require_user, visible_collection_criterion
from ..features import features
from ..models import Branch, Collection, Concept, ConceptRelation, User, Version
from ..serialize import user_out

router = APIRouter(tags=["meta"])


@router.get("/features")
def feature_flags() -> dict[str, bool]:
    """Which feature flags are on (server/app/features.py). Public: the web
    reads the same variables from its own container, this is the audit view."""
    return features()


@router.get("/users", response_model=list[schemas.UserOut])
def search_users(
    q: str = "",
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[schemas.UserOut]:
    """Search users by handle or display name. Login-gated (säkerhetsfix
    2026-07-15) — the directory is not exposed to anonymous callers."""
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.handle.ilike(like), User.display_name.ilike(like)))
    users = query.order_by(User.display_name.asc()).limit(limit).all()
    return [out for out in (user_out(u) for u in users) if out is not None]


@router.get("/stats", response_model=schemas.StatsOut)
def stats(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.StatsOut:
    """Counts only content in collections the caller may see (iteration 3):
    org_private material is not disclosed via aggregates. Users stay global."""
    visible = visible_collection_criterion(user)
    collections = db.query(func.count()).select_from(Collection).filter(visible).scalar() or 0
    concepts = (
        db.query(func.count())
        .select_from(Concept)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible)
        .scalar()
        or 0
    )
    versions = (
        db.query(func.count())
        .select_from(Version)
        .join(Concept, Concept.id == Version.concept_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible)
        .scalar()
        or 0
    )
    relations = (
        db.query(func.count())
        .select_from(ConceptRelation)
        .join(Concept, Concept.id == ConceptRelation.from_concept_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible)
        .scalar()
        or 0
    )
    users = db.query(func.count()).select_from(User).scalar() or 0
    return schemas.StatsOut(
        collections=collections,
        concepts=concepts,
        versions=versions,
        relations=relations,
        users=users,
    )


@router.get("/tags", response_model=list[schemas.TagCountOut])
def list_tags(
    q: str = "",
    collection: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.TagCountOut]:
    """Distinct tags from main-branch heads in visible collections, with usage
    counts — feeds the TagEditor autosuggest and the search-filter tag list.
    Suggestion-driven convergence: the vocabulary tightens because editors SEE
    what already exists, not because free text is forbidden."""
    # Aggregation happens in SQLite via json_each (Bengt #3) — no Python-side
    # full-corpus Counter on the autosuggest hot path.
    tag_expr = func.json_each(Version.tags).table_valued("value", joins_implicitly=True)
    query = (
        db.query(tag_expr.c.value, func.count().label("uses"))
        .select_from(Version)
        .join(Branch, (Branch.head_version_id == Version.id) & (Branch.name == "main"))
        .join(Concept, Concept.id == Version.concept_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible_collection_criterion(user))
    )
    if collection:
        slugs = [s.strip() for s in collection.split(",") if s.strip()]
        if slugs:
            query = query.filter(Collection.slug.in_(slugs))
    needle = q.strip().lower()
    if needle:
        query = query.filter(func.lower(tag_expr.c.value).like(f"%{needle}%"))
    rows = (
        query.group_by(tag_expr.c.value)
        .order_by(func.count().desc(), func.lower(tag_expr.c.value).asc())
        .limit(limit)
        .all()
    )
    return [schemas.TagCountOut(name=name, count=count) for name, count in rows]
