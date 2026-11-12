"""Concept endpoints — including the Time Machine payload (/graph)."""


import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, aliased, joinedload

from .. import graph, schemas
from ..db import get_db
from ..deps import (
    can_view_collection,
    current_user,
    ensure_write_allowed,
    visible_collection_criterion,
)
from ..errors import api_error
from ..models import (
    Branch,
    ChangeProposal,
    Collection,
    Comment,
    Concept,
    ConceptRelation,
    ConceptTaxonomyValue,
    Endorsement,
    LegacyId,
    ListItem,
    PinList,
    Taxonomy,
    TaxonomyValue,
    User,
    Version,
    VersionEdge,
    Watch,
)
from ..serialize import collection_out, version_out
from .collab import count_events

router = APIRouter(prefix="/concepts", tags=["concepts"])


_MD_LINK = re.compile(r"\[([^\]]+)\]\([^()\s]+\)")
_MD_XREF_LABELLED = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
_MD_XREF = re.compile(r"\[\[([^\]]+)\]\]")
_MD_EMPHASIS = re.compile(r"\*{1,2}([^*]+)\*{1,2}")
_MD_HEADING = re.compile(r"^#+\s*", re.MULTILINE)


def _strip_markdown(text: str) -> str:
    """Snippets are plain text: reduce links/cross-refs to their labels and
    drop emphasis markers BEFORE truncation, so a cut can never land inside
    markup syntax (mirrors web/src/lib/text.ts stripMarkdown)."""
    text = _MD_XREF_LABELLED.sub(r"\2", text)
    text = _MD_XREF.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_EMPHASIS.sub(r"\1", text)
    return _MD_HEADING.sub("", text)


def _snippet(text: str, length: int = 220) -> str:
    text = " ".join(_strip_markdown(text).split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


_LINK_TOKEN = re.compile(r"\[\[[^\]]+\]\]|\[[^\]]+\]\([^)\s]+\)|\S+")


def _snippet_md(text: str, max_words: int = 32) -> str:
    """Trunkera till ~max_words ord men bevara markdown-länkar/korsreferenser
    som atomära tokens (v1:s truncateMarkdown, porterad — kontraktets
    princip 7: klickbara länkar i kortens definitionsutdrag)."""
    # rubrikmarkörer renderar illa i kortutdrag
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    tokens = _LINK_TOKEN.findall(" ".join(text.split()))
    if len(tokens) <= max_words:
        return " ".join(tokens)
    return " ".join(tokens[:max_words]).rstrip(",;:") + " …"


def _get_concept(db: Session, concept_id: str, user: User | None = None) -> Concept:
    """Fetch a concept; org_private collections 404 for outsiders (not 403 —
    their existence is not disclosed). Prototype term_ids resolve through the
    legacy_ids alias table — imported definitions link with the old ids and
    versions are immutable, so the lookup translates instead (migrate_006)."""
    concept = db.get(Concept, concept_id)
    if concept is None:
        legacy = db.get(LegacyId, concept_id)
        if legacy is not None:
            concept = db.get(Concept, legacy.concept_id)
    if concept is None or not can_view_collection(user, concept.collection):
        raise api_error(404, "concept_not_found", "Concept not found")
    return concept


def _require_edit(user: User | None, collection: Collection) -> None:
    """Concept/version writes: the shared night-3 guard — 401 anonymous,
    403 inactive/suspended/rights, 423 archived/locked."""
    ensure_write_allowed(user, collection)


def _write_provenance(user: User | None) -> dict | None:
    """Anonymous wiki-mode writes (edit_policy 'open') are marked in
    provenance; identified writes keep the graph service's default."""
    return {"kind": "human", "anonymous": True} if user is None else None


def _taxonomies_for(db: Session, concept: Concept) -> list[schemas.ConceptTaxonomyOut]:
    """The concept's assigned taxonomy values, grouped per taxonomy (global +
    the collection's own). Assignment lives on the CONCEPT — see taxonomies.py."""
    rows = (
        db.query(TaxonomyValue, Taxonomy)
        .join(Taxonomy, Taxonomy.id == TaxonomyValue.taxonomy_id)
        .join(ConceptTaxonomyValue, ConceptTaxonomyValue.value_id == TaxonomyValue.id)
        .filter(ConceptTaxonomyValue.concept_id == concept.id)
        .order_by(Taxonomy.created_at.asc(), TaxonomyValue.position.asc())
        .all()
    )
    grouped: dict[str, schemas.ConceptTaxonomyOut] = {}
    for value, taxonomy in rows:
        out = grouped.setdefault(
            taxonomy.id,
            schemas.ConceptTaxonomyOut(
                taxonomy_id=taxonomy.id,
                taxonomy_slug=taxonomy.slug,
                taxonomy_name=taxonomy.name,
                scope=taxonomy.scope,
                max_per_concept=taxonomy.max_per_concept,
            ),
        )
        out.values.append(
            schemas.TaxonomyValueOut(
                id=value.id, name=value.name, name_en=value.name_en, position=value.position
            )
        )
    return list(grouped.values())


def _global_categories_by_concept(
    db: Session, concept_ids: list[str]
) -> dict[str, list[tuple[str, str | None]]]:
    """Bulk lookup for list rendering: concept_id → (name, name_en) pairs."""
    if not concept_ids:
        return {}
    rows = (
        db.query(ConceptTaxonomyValue.concept_id, TaxonomyValue.name, TaxonomyValue.name_en)
        .join(TaxonomyValue, TaxonomyValue.id == ConceptTaxonomyValue.value_id)
        .join(Taxonomy, Taxonomy.id == TaxonomyValue.taxonomy_id)
        .filter(
            ConceptTaxonomyValue.concept_id.in_(concept_ids),
            Taxonomy.scope == "global",
        )
        .order_by(TaxonomyValue.position.asc())
        .all()
    )
    result: dict[str, list[tuple[str, str | None]]] = {}
    for concept_id, name, name_en in rows:
        result.setdefault(concept_id, []).append((name, name_en))
    return result


@router.get("", response_model=schemas.ConceptListOut)
def list_concepts(
    q: str | None = None,
    collection: str | None = None,
    language: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ConceptListOut:
    query = (
        db.query(Concept, Version, Collection)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible_collection_criterion(user))
    )
    if collection:
        # Comma-separated slugs — OR within the filter type (search filters).
        slugs = [s.strip() for s in collection.split(",") if s.strip()]
        if slugs:
            query = query.filter(Collection.slug.in_(slugs))
    if language:
        query = query.filter(Version.language == language)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        # 'endorsed' is no longer a version status (rework 2026-07-11) — the
        # filter value survives for URL/UI compat and means "some version of
        # the concept carries an ACTIVE endorsement".
        wants_endorsed = "endorsed" in statuses
        statuses = [s for s in statuses if s != "endorsed"]
        clauses = []
        if statuses:
            clauses.append(Version.status.in_(statuses))
        if wants_endorsed:
            endorsed_version = aliased(Version)
            clauses.append(
                db.query(Endorsement)
                .join(endorsed_version, Endorsement.version_id == endorsed_version.id)
                .filter(
                    endorsed_version.concept_id == Concept.id,
                    Endorsement.withdrawn_at.is_(None),
                )
                .exists()
            )
        if clauses:
            query = query.filter(or_(*clauses))
    if tag:
        # Tags are a JSON array; match the exact element via its quoted JSON
        # form so total/pagination reflect the filter (not a page post-filter).
        # Comma-separated values — OR within the filter type.
        tag_clauses = [
            cast(Version.tags, String).like(f'%"{t.strip()}"%')
            for t in tag.split(",")
            if t.strip()
        ]
        if tag_clauses:
            query = query.filter(or_(*tag_clauses))
    if category:
        # Comma-separated taxonomy-value ids (global categories) — OR within
        # the type: the concept carries ANY of the values.
        value_ids = [c.strip() for c in category.split(",") if c.strip()]
        if value_ids:
            query = query.filter(
                db.query(ConceptTaxonomyValue)
                .filter(
                    ConceptTaxonomyValue.concept_id == Concept.id,
                    ConceptTaxonomyValue.value_id.in_(value_ids),
                )
                .exists()
            )
    rank = None
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Version.canonical_form.ilike(like), Version.definition_md.ilike(like))
        )
        # Relevance ranking (2026-07-11): exact name match first, then
        # name-prefix, then name-contains, and definition-only matches last;
        # alphabetical within each band.
        from sqlalchemy import case, func

        lowered = func.lower(Version.canonical_form)
        needle = q.lower()
        rank = case(
            (lowered == needle, 0),
            (lowered.like(f"{needle}%"), 1),
            (lowered.like(f"%{needle}%"), 2),
            else_=3,
        )
    total = query.count()
    order = (rank, Version.canonical_form.asc()) if rank is not None else (
        Version.canonical_form.asc(),
    )
    rows = query.order_by(*order).offset(offset).limit(limit).all()

    version_counts: dict[str, int] = {}
    concept_ids = [c.id for c, _, _ in rows]
    if concept_ids:
        from sqlalchemy import func

        for concept_id, count in (
            db.query(Version.concept_id, func.count(Version.id))
            .filter(Version.concept_id.in_(concept_ids))
            .group_by(Version.concept_id)
            .all()
        ):
            version_counts[concept_id] = count

    categories_by_concept = _global_categories_by_concept(db, concept_ids)
    items = []
    for concept, head, coll in rows:
        cats = categories_by_concept.get(concept.id, [])
        # Display-level dedup (2026-07-12): prototype imports stored v1
        # category names as version TAGS — hide tags that merely duplicate a
        # curated category (matched in either language; history untouched).
        cat_names = {name.lower() for pair in cats for name in pair if name}
        tags = [
            tag
            for tag in (head.tags or [])
            if tag.lower() not in cat_names and not tag.startswith("part:")
        ]
        items.append(
            schemas.ConceptListItem(
                id=concept.id,
                canonical_form=head.canonical_form,
                language=head.language,
                definition_snippet=_snippet(head.definition_md),
                definition_snippet_md=_snippet_md(head.definition_md),
                tags=tags,
                categories=[name for name, _en in cats],
                status=head.status,
                collection_slug=coll.slug,
                collection_name=coll.name,
                collection_year=coll.year,
                collection_visibility=coll.visibility,
                collection_has_org=coll.organisation_id is not None,
                version_count=version_counts.get(concept.id, 1),
                updated_at=head.created_at,
            )
        )
    return schemas.ConceptListOut(items=items, total=total)


def _relations_for(db: Session, concept: Concept) -> list[schemas.RelationOut]:
    relations = (
        db.query(ConceptRelation)
        .filter(
            or_(
                ConceptRelation.from_concept_id == concept.id,
                ConceptRelation.to_concept_id == concept.id,
            )
        )
        .all()
    )
    out: list[schemas.RelationOut] = []
    for rel in relations:
        direction = "out" if rel.from_concept_id == concept.id else "in"
        other_id = rel.to_concept_id if direction == "out" else rel.from_concept_id
        other = db.get(Concept, other_id)
        if other is None:
            continue
        head = graph.head_of(db, other)
        out.append(
            schemas.RelationOut(
                id=rel.id,
                relation_type=rel.relation_type,
                direction=direction,
                other_concept_id=other_id,
                other_canonical_form=head.canonical_form if head else "?",
                other_collection_slug=other.collection.slug,
                note=rel.note,
            )
        )
    return out


def _translations_for(db: Session, concept: Concept) -> list[schemas.TranslationOut]:
    """Translations = translated_from edges touching any of this concept's versions."""
    version_ids = [v.id for v in concept.versions]
    if not version_ids:
        return []
    edges = (
        db.query(VersionEdge)
        .filter(
            VersionEdge.edge_type == "translated_from",
            or_(
                VersionEdge.child_id.in_(version_ids),
                VersionEdge.parent_id.in_(version_ids),
            ),
        )
        .all()
    )
    seen: set[str] = set()
    out: list[schemas.TranslationOut] = []
    for edge in edges:
        local = edge.child_id in version_ids
        other_version = db.get(Version, edge.parent_id if local else edge.child_id)
        if other_version is None or other_version.concept_id == concept.id:
            continue
        if other_version.concept_id in seen:
            continue
        seen.add(other_version.concept_id)
        other_concept = db.get(Concept, other_version.concept_id)
        head = graph.head_of(db, other_concept) if other_concept else None
        shown = head or other_version
        out.append(
            schemas.TranslationOut(
                concept_id=other_version.concept_id,
                version_id=shown.id,
                language=shown.language,
                canonical_form=shown.canonical_form,
            )
        )
    return out


def _concept_counters(db: Session, concept: Concept, user: User | None) -> dict[str, int]:
    """The six engagement counters for the concept page (begreppssidans
    omgörning, 2026-07). `list_count` is the CALLER's own pin_lists only —
    0 for anonymous, since an anonymous caller has no lists to own."""
    watcher_count = db.query(Watch).filter(Watch.concept_id == concept.id).count()
    if user is None:
        list_count = 0
    else:
        list_count = (
            db.query(PinList.id)
            .join(ListItem, ListItem.list_id == PinList.id)
            .filter(PinList.owner_id == user.id, ListItem.concept_id == concept.id)
            .distinct()
            .count()
        )
    comment_count = (
        db.query(Comment)
        .filter(Comment.concept_id == concept.id, Comment.proposal_id.is_(None))
        .count()
    )
    proposal_count = (
        db.query(ChangeProposal).filter(ChangeProposal.concept_id == concept.id).count()
    )
    open_proposal_count = (
        db.query(ChangeProposal)
        .filter(ChangeProposal.concept_id == concept.id, ChangeProposal.status == "open")
        .count()
    )
    activity_count = count_events(db, [concept.id])
    return {
        "watcher_count": watcher_count,
        "list_count": list_count,
        "comment_count": comment_count,
        "proposal_count": proposal_count,
        "open_proposal_count": open_proposal_count,
        "activity_count": activity_count,
    }


@router.get("/most-watched", response_model=list[schemas.MostWatchedOut])
def most_watched_concepts(
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.MostWatchedOut]:
    """Home page 'most watched' strip. MUST stay registered before
    `/{concept_id}` — otherwise "most-watched" is swallowed as a concept id.
    Visibility filtering reuses the exact same helper as every other read
    path (`visible_collection_criterion`): org_private collections are
    invisible unless the caller is a member (or super admin)."""
    watcher_count_col = func.count(Watch.user_id)
    rows = (
        db.query(Concept, Version, Collection, watcher_count_col.label("watcher_count"))
        .join(Watch, Watch.concept_id == Concept.id)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(visible_collection_criterion(user))
        .group_by(Concept.id)
        .having(watcher_count_col >= 1)
        .order_by(watcher_count_col.desc(), Version.canonical_form.asc())
        .limit(limit)
        .all()
    )
    return [
        schemas.MostWatchedOut(
            id=concept.id,
            canonical_form=version.canonical_form,
            language=version.language,
            watcher_count=watcher_count,
            collection=schemas.VersionCollectionRefOut(
                slug=coll.slug,
                name=coll.name,
                year=coll.year,
                visibility=coll.visibility,
                has_org=coll.organisation_id is not None,
            ),
        )
        for concept, version, coll, watcher_count in rows
    ]


@router.get("/{concept_id}", response_model=schemas.ConceptOut)
def get_concept(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ConceptOut:
    concept = _get_concept(db, concept_id, user)
    head = graph.head_of(db, concept)
    watching = (
        user is not None
        and db.get(Watch, {"user_id": user.id, "concept_id": concept.id}) is not None
    )
    return schemas.ConceptOut(
        id=concept.id,
        collection=collection_out(concept.collection, user=user),
        created_at=concept.created_at,
        head=version_out(head) if head else None,
        branches=[
            schemas.BranchOut(id=b.id, name=b.name, head_version_id=b.head_version_id)
            for b in concept.branches
        ],
        relations=_relations_for(db, concept),
        translations=_translations_for(db, concept),
        version_count=len(concept.versions),
        watching=watching,
        taxonomies=_taxonomies_for(db, concept),
        **_concept_counters(db, concept, user),
    )


@router.get("/{concept_id}/graph", response_model=schemas.ConceptGraphOut)
def get_concept_graph(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ConceptGraphOut:
    """The Time Machine payload: every version in full, every edge, every branch."""
    concept = _get_concept(db, concept_id, user)
    versions = (
        db.query(Version)
        .options(joinedload(Version.annotations), joinedload(Version.endorsements))
        .filter(Version.concept_id == concept.id)
        .order_by(Version.created_at.asc())
        .all()
    )
    user_ids = {v.created_by for v in versions if v.created_by}
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    version_ids = [v.id for v in versions]
    edges = (
        db.query(VersionEdge).filter(VersionEdge.child_id.in_(version_ids)).all()
        if version_ids
        else []
    )
    return schemas.ConceptGraphOut(
        concept_id=concept.id,
        collection=collection_out(concept.collection, user=user),
        versions=[version_out(v, users=users) for v in versions],
        edges=[
            schemas.EdgeOut(
                child_id=e.child_id,
                parent_id=e.parent_id,
                edge_type=e.edge_type,
                ordinal=e.ordinal,
                note=e.note,
            )
            for e in edges
        ],
        branches=[
            schemas.BranchOut(id=b.id, name=b.name, head_version_id=b.head_version_id)
            for b in concept.branches
        ],
    )


@router.post("", response_model=schemas.ConceptOut, status_code=201)
def create_concept(
    payload: schemas.ConceptCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ConceptOut:
    collection = db.get(Collection, payload.collection_id)
    if collection is None or not can_view_collection(user, collection):
        raise api_error(404, "collection_not_found", "Collection not found")
    _require_edit(user, collection)
    concept, _version, _branch = graph.create_concept(
        db,
        collection_id=payload.collection_id,
        canonical_form=payload.canonical_form,
        language=payload.language,
        definition_md=payload.definition_md,
        status=payload.status,
        tags=payload.tags,
        note=payload.note,
        provenance=_write_provenance(user),
        created_by=user.id if user else None,
        translated_from_version_id=payload.translated_from_version_id,
        spawned_from_id=payload.spawned_from_id,
    )
    db.commit()
    return get_concept(concept.id, db, user)


@router.post("/{concept_id}/versions", response_model=schemas.VersionOut, status_code=201)
def create_version(
    concept_id: str,
    payload: schemas.VersionCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.VersionOut:
    concept = _get_concept(db, concept_id, user)
    # mode=branch is exempt from the collection lock for any authed identity —
    # branching is how locked content evolves (VISION §4.3, iteration 4).
    ensure_write_allowed(
        user, concept.collection, branch_exempt=payload.mode == "branch"
    )
    version = graph.add_version(
        db,
        concept=concept,
        mode=payload.mode,
        base_version_id=payload.base_version_id,
        canonical_form=payload.canonical_form,
        definition_md=payload.definition_md,
        language=payload.language,
        status=payload.status,
        tags=payload.tags,
        note=payload.note,
        provenance=_write_provenance(user),
        created_by=user.id if user else None,
        branch_name=payload.branch_name,
        extra_parent_ids=payload.extra_parent_ids,
        source_version_id=payload.source_version_id,
    )
    db.commit()
    return version_out(version)


@router.post("/{concept_id}/promote", response_model=schemas.VersionOut, status_code=201)
def promote_version(
    concept_id: str,
    payload: schemas.PromoteIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.VersionOut:
    concept = _get_concept(db, concept_id, user)
    _require_edit(user, concept.collection)
    version = graph.promote(
        db,
        concept=concept,
        version_id=payload.version_id,
        note=payload.note,
        created_by=user.id if user else None,
        branch_name=payload.branch_name,
        canonical_form=payload.canonical_form,
        definition_md=payload.definition_md,
        tags=payload.tags,
        status=payload.status,
    )
    db.commit()
    return version_out(version)
