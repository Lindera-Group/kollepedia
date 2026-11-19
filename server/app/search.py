"""Concept search — the one definition of what matches a query and in what order.

GET /concepts (the search field and the browse list on the site) and the
public MCP tool ``search_concepts`` both build their query here, so the same
question gives the same concepts in the same order whichever way it is asked.

Order: exact name first, then names that start with the query, names that
contain it, and last the concepts where only the definition matches;
alphabetical within each band. Equal names — the same term in several
collections, or twice in one — come in the order they entered the bank (the
main branch's creation time), with the concept id as the final word. The
order is therefore total: paging neither repeats nor skips an entry, and two
callers always agree.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, case, func, or_
from sqlalchemy.orm import Query, Session

from .deps import visible_collection_criterion
from .models import Branch, Collection, Concept, User, Version


def head_query(db: Session, user: User | None) -> Query:
    """(Concept, head Version, Collection) for every concept `user` may see;
    None is an anonymous visitor."""
    return (
        db.query(Concept, Version, Collection)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible_collection_criterion(user))
    )


def in_collections(query: Query, collection: str | None) -> Query:
    """Narrow a head_query to one collection slug, or to any of several
    comma-separated ones."""
    slugs = [s.strip() for s in (collection or "").split(",") if s.strip()]
    return query.filter(Collection.slug.in_(slugs)) if slugs else query


def text_search(query: Query, q: str | None) -> tuple[Query, tuple[ColumnElement, ...]]:
    """Narrow a head_query to the concepts whose name or definition contains
    `q`, and return it with the ORDER BY that belongs to it (module docstring).
    Surrounding whitespace is ignored; without a query every concept matches,
    alphabetically."""
    alphabetical = (Version.canonical_form.asc(), Branch.created_at.asc(), Concept.id.asc())
    needle = (q or "").strip()
    if not needle:
        return query, alphabetical
    like = f"%{needle}%"
    query = query.filter(
        or_(Version.canonical_form.ilike(like), Version.definition_md.ilike(like))
    )
    name = func.lower(Version.canonical_form)
    lowered = needle.lower()
    rank = case(
        (name == lowered, 0),
        (name.like(f"{lowered}%"), 1),
        (name.like(f"%{lowered}%"), 2),
        else_=3,
    )
    return query, (rank, *alphabetical)
