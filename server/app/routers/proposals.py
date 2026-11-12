"""Change proposals — "PR för begrepp" (VISION §10, iteration 4).

A proposal asks the collection's stewards to merge a named branch into main.
Creation is open to any authenticated identity (paired with the night-4 rule
that mode=branch version-writes are allowed even in locked collections — this
is how locked content evolves). Resolution rights: collection manage, i.e.
owning-org admin / creator of an org-less collection / super admin.

Merging NEVER bypasses the graph service:
- fast-forward (target head still == branch point): a new main version via
  add_version(mode='revise') copying the source head, `revised_from` target;
- otherwise an explicit synthesis via add_version(mode='synthesize') with
  parents [target head, source head], still copying the source head content —
  the resolver said "take the branch", and lineage records both strands.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import graph, schemas
from ..db import get_db
from ..deps import can_manage_collection, can_view_collection, current_user, ensure_actor_can_write
from ..errors import api_error
from ..models import (
    Branch,
    ChangeProposal,
    Collection,
    Concept,
    User,
    Version,
    VersionEdge,
    utcnow,
)
from ..serialize import user_out, version_out

router = APIRouter(tags=["proposals"])


class ProposalCreateIn(BaseModel):
    branch_name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=schemas.DESCRIPTION_MAX)


class ResolutionIn(BaseModel):
    note: str = Field(min_length=1, max_length=schemas.NOTE_MAX)


def _get_visible_concept(db: Session, concept_id: str, user: User | None) -> Concept:
    concept = db.get(Concept, concept_id)
    if concept is None or not can_view_collection(user, concept.collection):
        raise api_error(404, "concept_not_found", "Concept not found")
    return concept


def _get_visible_proposal(db: Session, proposal_id: str, user: User | None) -> ChangeProposal:
    proposal = db.get(ChangeProposal, proposal_id)
    if proposal is None or not can_view_collection(user, proposal.concept.collection):
        raise api_error(404, "proposal_not_found", "Proposal not found")
    return proposal


def _branch_base_id(db: Session, branch: Branch) -> str | None:
    """The branch point: the parent of the branch's root version via its
    branched_from edge (created together with the branch, app.graph)."""
    edge = (
        db.query(VersionEdge)
        .join(Version, Version.id == VersionEdge.child_id)
        .filter(
            Version.branch_id == branch.id,
            VersionEdge.edge_type == "branched_from",
        )
        .order_by(Version.created_at.asc())
        .first()
    )
    return edge.parent_id if edge else None


def _head_version(db: Session, branch: Branch | None) -> Version | None:
    if branch is None or branch.head_version_id is None:
        return None
    return db.get(Version, branch.head_version_id)


def _main_branch(db: Session, proposal: ChangeProposal) -> Branch | None:
    return (
        db.query(Branch)
        .filter(Branch.concept_id == proposal.concept_id, Branch.name == proposal.target_branch)
        .first()
    )


def proposal_out(db: Session, proposal: ChangeProposal) -> schemas.ProposalOut:
    concept = proposal.concept
    source_branch = proposal.source_branch
    source_head = _head_version(db, source_branch)
    target_head = _head_version(db, _main_branch(db, proposal))
    created_by = db.get(User, proposal.created_by) if proposal.created_by else None
    resolved_by = db.get(User, proposal.resolved_by) if proposal.resolved_by else None
    return schemas.ProposalOut(
        id=proposal.id,
        concept_id=proposal.concept_id,
        canonical_form=target_head.canonical_form if target_head else "?",
        collection_slug=concept.collection.slug,
        source_branch_name=source_branch.name if source_branch else "?",
        target_branch=proposal.target_branch,
        title=proposal.title,
        description=proposal.description,
        status=proposal.status,
        created_by=user_out(created_by),
        created_at=proposal.created_at,
        resolved_by=user_out(resolved_by),
        resolved_at=proposal.resolved_at,
        resolution_note=proposal.resolution_note,
        source_head=version_out(source_head) if source_head else None,
        target_head=version_out(target_head) if target_head else None,
        base_version_id=_branch_base_id(db, source_branch) if source_branch else None,
    )


@router.post(
    "/concepts/{concept_id}/proposals", response_model=schemas.ProposalOut, status_code=201
)
def create_proposal(
    concept_id: str,
    payload: ProposalCreateIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ProposalOut:
    if user is None:
        raise api_error(401, "login_required", "Login required")
    ensure_actor_can_write(user)
    concept = _get_visible_concept(db, concept_id, user)
    if concept.collection.is_archived:
        raise api_error(
            423,
            "collection_archived",
            "Collection is archived — unarchive it to make changes.",
        )
    branch_name = payload.branch_name.strip()
    if branch_name == "main":
        raise api_error(
            422, "proposal_source_is_main", "A proposal must start from a branch other than main."
        )
    branch = (
        db.query(Branch)
        .filter(Branch.concept_id == concept.id, Branch.name == branch_name)
        .first()
    )
    if branch is None:
        raise api_error(
            404,
            "branch_not_found",
            f"Branch '{branch_name}' not found on this concept.",
            branch_name=branch_name,
        )
    open_existing = (
        db.query(ChangeProposal)
        .filter(
            ChangeProposal.source_branch_id == branch.id,
            ChangeProposal.status == "open",
        )
        .first()
    )
    if open_existing is not None:
        raise api_error(
            409, "proposal_already_open", "The branch already has an open change proposal."
        )
    proposal = ChangeProposal(
        concept_id=concept.id,
        source_branch_id=branch.id,
        target_branch="main",
        title=payload.title.strip(),
        description=payload.description,
        created_by=user.id,
    )
    db.add(proposal)
    db.commit()
    return proposal_out(db, proposal)


@router.get("/proposals", response_model=list[schemas.ProposalOut])
def list_proposals(
    status: str | None = None,
    collection: str | None = None,
    concept_id: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.ProposalOut]:
    query = db.query(ChangeProposal).join(Concept, Concept.id == ChangeProposal.concept_id)
    if status:
        query = query.filter(ChangeProposal.status == status)
    if concept_id:
        query = query.filter(ChangeProposal.concept_id == concept_id)
    if collection:
        query = query.join(Collection, Collection.id == Concept.collection_id).filter(
            Collection.slug == collection
        )
    proposals = query.order_by(ChangeProposal.created_at.desc()).limit(200).all()
    return [
        proposal_out(db, p) for p in proposals if can_view_collection(user, p.concept.collection)
    ]


@router.get("/proposals/{proposal_id}", response_model=schemas.ProposalOut)
def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ProposalOut:
    return proposal_out(db, _get_visible_proposal(db, proposal_id, user))


def _require_resolution_rights(db: Session, proposal: ChangeProposal, user: User | None) -> User:
    """Merge/reject rights: collection manage — owning-org admin, creator of
    an org-less collection, or super admin."""
    if user is None:
        raise api_error(401, "login_required", "Login required")
    ensure_actor_can_write(user)
    collection = proposal.concept.collection
    if not can_manage_collection(user, collection):
        raise api_error(
            403,
            "proposal_resolve_forbidden",
            "Only the collection's stewards (owning-org admins or super admins) "
            "can resolve proposals.",
        )
    if collection.is_archived:
        raise api_error(
            423,
            "collection_archived",
            "Collection is archived — unarchive it to make changes.",
        )
    return user


def _require_open(proposal: ChangeProposal) -> None:
    if proposal.status != "open":
        raise api_error(
            409,
            "proposal_closed",
            f"Proposal is already resolved ({proposal.status}).",
            status=proposal.status,
        )


@router.post("/proposals/{proposal_id}/merge", response_model=schemas.ProposalOut)
def merge_proposal(
    proposal_id: str,
    payload: ResolutionIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ProposalOut:
    proposal = _get_visible_proposal(db, proposal_id, user)
    actor = _require_resolution_rights(db, proposal, user)
    _require_open(proposal)

    concept = proposal.concept
    source_head = _head_version(db, proposal.source_branch)
    main = _main_branch(db, proposal)
    target_head = _head_version(db, main)
    if source_head is None or target_head is None:
        raise api_error(
            409, "proposal_missing_head", "Proposal is missing its source or target version."
        )
    base_version_id = _branch_base_id(db, proposal.source_branch)
    note = payload.note.strip()
    provenance = {"kind": "human", "merged_from_proposal": proposal.id}

    if base_version_id == target_head.id:
        # Fast-forward: main has not moved since the branch point — copy the
        # source head onto main as a plain revision of the target head.
        graph.add_version(
            db,
            concept=concept,
            mode="revise",
            base_version_id=target_head.id,
            canonical_form=source_head.canonical_form,
            definition_md=source_head.definition_md,
            language=source_head.language,
            status=source_head.status,
            tags=list(source_head.tags or []),
            note=note,
            provenance=provenance,
            created_by=actor.id,
        )
    else:
        # Main moved: an explicit synthesis with parents [target head, source
        # head] — content still copies the source head (the resolver's call).
        graph.add_version(
            db,
            concept=concept,
            mode="synthesize",
            base_version_id=target_head.id,
            extra_parent_ids=[source_head.id],
            canonical_form=source_head.canonical_form,
            definition_md=source_head.definition_md,
            language=source_head.language,
            status=source_head.status,
            tags=list(source_head.tags or []),
            note=note,
            provenance=provenance,
            created_by=actor.id,
        )

    proposal.status = "merged"
    proposal.resolved_by = actor.id
    proposal.resolved_at = utcnow()
    proposal.resolution_note = note
    db.commit()
    return proposal_out(db, proposal)


@router.post("/proposals/{proposal_id}/reject", response_model=schemas.ProposalOut)
def reject_proposal(
    proposal_id: str,
    payload: ResolutionIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ProposalOut:
    proposal = _get_visible_proposal(db, proposal_id, user)
    actor = _require_resolution_rights(db, proposal, user)
    _require_open(proposal)
    proposal.status = "rejected"
    proposal.resolved_by = actor.id
    proposal.resolved_at = utcnow()
    proposal.resolution_note = payload.note.strip()
    db.commit()
    return proposal_out(db, proposal)


@router.post("/proposals/{proposal_id}/withdraw", response_model=schemas.ProposalOut)
def withdraw_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.ProposalOut:
    proposal = _get_visible_proposal(db, proposal_id, user)
    if user is None:
        raise api_error(401, "login_required", "Login required")
    if not user.is_super_admin and proposal.created_by != user.id:
        raise api_error(
            403, "proposal_withdraw_forbidden", "Only the proposer can withdraw the proposal."
        )
    _require_open(proposal)
    proposal.status = "withdrawn"
    proposal.resolved_by = user.id
    proposal.resolved_at = utcnow()
    db.commit()
    return proposal_out(db, proposal)
