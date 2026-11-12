"""Discussions, watching and computed activity (iteration 4).

- Comments are flat, attached to a concept and optionally to a proposal.
  Reading follows collection visibility; posting requires an authenticated
  identity; deleting is author-or-super.
- Watch is a plain (user, concept) subscription; the `watching` flag in
  ConceptOut is computed for the caller.
- Activity is COMPUTED — no event table. Each source (versions, endorsements,
  comments, proposals opened/resolved) contributes a limit-bounded,
  newest-first query; the slices are merge-sorted in Python and cut to the
  requested limit. That keeps every query index-friendly and the result exact
  for the first `limit` items. `count_events` mirrors the same five sources
  without the limit, for exact totals (concepts.py's `activity_count`,
  `/activity/unseen-count`).
- Begreppssidans omgörning (2026-07): each row also carries `version_id`
  (the version it concerns — null for comments) and version rows are
  classified `version` | `branch` | `merge` from the version graph (see
  `_version_kinds`), not just tagged `version`.
- `users.activity_seen_at` (migration 009) backs the header bell:
  `/activity/unseen-count` counts events newer than it (NULL = everything),
  `/activity/seen` stamps it to now().
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.orm import Query as OrmQuery

from .. import schemas
from ..db import get_db
from ..deps import can_view_collection, current_user, ensure_actor_can_write, require_user
from ..errors import api_error
from ..models import (
    Branch,
    ChangeProposal,
    Comment,
    Concept,
    Endorsement,
    User,
    Version,
    VersionEdge,
    Watch,
    utcnow,
)
from ..serialize import user_out

router = APIRouter(tags=["collab"])

COMMENT_MAX_CHARS = 4000


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=COMMENT_MAX_CHARS)


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


def _comment_out(comment: Comment, users: dict[str, User]) -> schemas.CommentOut:
    return schemas.CommentOut(
        id=comment.id,
        concept_id=comment.concept_id,
        proposal_id=comment.proposal_id,
        body=comment.body,
        created_by=user_out(users.get(comment.created_by) if comment.created_by else None),
        created_at=comment.created_at,
    )


def _comments_out(db: Session, comments: list[Comment]) -> list[schemas.CommentOut]:
    user_ids = {c.created_by for c in comments if c.created_by}
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    return [_comment_out(c, users) for c in comments]


# ── Comments ──


@router.get("/concepts/{concept_id}/comments", response_model=list[schemas.CommentOut])
def list_concept_comments(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.CommentOut]:
    concept = _get_visible_concept(db, concept_id, user)
    comments = (
        db.query(Comment)
        .filter(Comment.concept_id == concept.id, Comment.proposal_id.is_(None))
        .order_by(Comment.created_at.asc())
        .all()
    )
    return _comments_out(db, comments)


@router.post(
    "/concepts/{concept_id}/comments", response_model=schemas.CommentOut, status_code=201
)
def create_concept_comment(
    concept_id: str,
    payload: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.CommentOut:
    ensure_actor_can_write(user)
    concept = _get_visible_concept(db, concept_id, user)
    comment = Comment(concept_id=concept.id, body=payload.body, created_by=user.id)
    db.add(comment)
    db.commit()
    return _comment_out(comment, {user.id: user})


@router.get("/proposals/{proposal_id}/comments", response_model=list[schemas.CommentOut])
def list_proposal_comments(
    proposal_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.CommentOut]:
    proposal = _get_visible_proposal(db, proposal_id, user)
    comments = (
        db.query(Comment)
        .filter(Comment.proposal_id == proposal.id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return _comments_out(db, comments)


@router.post(
    "/proposals/{proposal_id}/comments", response_model=schemas.CommentOut, status_code=201
)
def create_proposal_comment(
    proposal_id: str,
    payload: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.CommentOut:
    ensure_actor_can_write(user)
    proposal = _get_visible_proposal(db, proposal_id, user)
    comment = Comment(
        concept_id=proposal.concept_id,
        proposal_id=proposal.id,
        body=payload.body,
        created_by=user.id,
    )
    db.add(comment)
    db.commit()
    return _comment_out(comment, {user.id: user})


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise api_error(404, "comment_not_found", "Comment not found")
    concept = db.get(Concept, comment.concept_id)
    if concept is not None and not can_view_collection(user, concept.collection):
        raise api_error(404, "comment_not_found", "Comment not found")
    if not user.is_super_admin and comment.created_by != user.id:
        raise api_error(
            403, "comment_delete_forbidden", "Only the author can delete the comment."
        )
    db.delete(comment)
    db.commit()


# ── Watching ──


@router.put("/concepts/{concept_id}/watch", status_code=204)
def watch_concept(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    concept = _get_visible_concept(db, concept_id, user)
    if db.get(Watch, {"user_id": user.id, "concept_id": concept.id}) is None:
        db.add(Watch(user_id=user.id, concept_id=concept.id))
        db.commit()


@router.delete("/concepts/{concept_id}/watch", status_code=204)
def unwatch_concept(
    concept_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    _get_visible_concept(db, concept_id, user)
    watch = db.get(Watch, {"user_id": user.id, "concept_id": concept_id})
    if watch is not None:
        db.delete(watch)
        db.commit()


# ── Computed activity ──


@dataclass
class _Event:
    kind: str
    at: datetime
    actor_id: str | None
    concept_id: str
    summary: str
    version_id: str | None = None


def _snippet(text: str, length: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _version_kinds(db: Session, version_ids: list[str]) -> dict[str, str]:
    """Classify each version as `branch` | `merge` | `version` for the
    history view's event layer (2026-07 correction to §4):
    - `branch`: its founding edge is `branched_from` (the first version of a
      newly created branch — app.graph mode='branch').
    - `merge`: more than one parent edge (synthesize's extra_parent_ids,
      a non-fast-forward proposal merge, or promote's dual lineage), OR its
      provenance carries `merged_from_proposal` (a fast-forward proposal
      merge — graph.add_version(mode='revise'), a single `revised_from`
      edge that is nonetheless a merge outcome).
    - everything else (plain revise/translate) stays `version`.
    """
    if not version_ids:
        return {}
    edges_by_child: dict[str, list[VersionEdge]] = {}
    for edge in (
        db.query(VersionEdge).filter(VersionEdge.child_id.in_(version_ids)).all()
    ):
        edges_by_child.setdefault(edge.child_id, []).append(edge)
    versions = (
        db.query(Version.id, Version.provenance)
        .filter(Version.id.in_(version_ids))
        .all()
    )
    kinds: dict[str, str] = {}
    for version_id, provenance in versions:
        parents = edges_by_child.get(version_id, [])
        if any(e.edge_type == "branched_from" for e in parents):
            kinds[version_id] = "branch"
        elif len(parents) > 1 or "merged_from_proposal" in (provenance or {}):
            kinds[version_id] = "merge"
        else:
            kinds[version_id] = "version"
    return kinds


def _collect_events(db: Session, concept_ids: list[str], limit: int) -> list[_Event]:
    """Limit-bounded newest-first slice per source, merge-sorted in Python."""
    events: list[_Event] = []

    versions = (
        db.query(Version)
        .filter(Version.concept_id.in_(concept_ids))
        .order_by(Version.created_at.desc())
        .limit(limit)
        .all()
    )
    version_kinds = _version_kinds(db, [v.id for v in versions])
    # Summaries are language-neutral payloads (the note, the title, the
    # comment) — the frontend prefixes a localized label per `kind`, so the
    # feed follows the UI language instead of baking in Swedish here.
    for v in versions:
        events.append(
            _Event(
                kind=version_kinds.get(v.id, "version"),
                at=v.created_at,
                actor_id=v.created_by,
                concept_id=v.concept_id,
                summary=v.note or v.canonical_form,
                version_id=v.id,
            )
        )

    endorsements = (
        db.query(Endorsement, Version.concept_id)
        .join(Version, Version.id == Endorsement.version_id)
        .filter(Version.concept_id.in_(concept_ids))
        .order_by(Endorsement.created_at.desc())
        .limit(limit)
        .all()
    )
    for endorsement, concept_id in endorsements:
        events.append(
            _Event(
                kind="endorsement",
                at=endorsement.created_at,
                actor_id=endorsement.stamped_by,
                concept_id=concept_id,
                summary=endorsement.body,
                version_id=endorsement.version_id,
            )
        )

    comments = (
        db.query(Comment)
        .filter(Comment.concept_id.in_(concept_ids))
        .order_by(Comment.created_at.desc())
        .limit(limit)
        .all()
    )
    for comment in comments:
        events.append(
            _Event(
                kind="comment",
                at=comment.created_at,
                actor_id=comment.created_by,
                concept_id=comment.concept_id,
                summary=_snippet(comment.body),
                version_id=None,
            )
        )

    opened = (
        db.query(ChangeProposal)
        .filter(ChangeProposal.concept_id.in_(concept_ids))
        .order_by(ChangeProposal.created_at.desc())
        .limit(limit)
        .all()
    )
    for proposal in opened:
        events.append(
            _Event(
                kind="proposal",
                at=proposal.created_at,
                actor_id=proposal.created_by,
                concept_id=proposal.concept_id,
                summary=proposal.title,
                version_id=_proposal_branch_head_id(proposal),
            )
        )

    resolved = (
        db.query(ChangeProposal)
        .filter(
            ChangeProposal.concept_id.in_(concept_ids),
            ChangeProposal.resolved_at.isnot(None),
        )
        .order_by(ChangeProposal.resolved_at.desc())
        .limit(limit)
        .all()
    )
    for proposal in resolved:
        # Distinct kinds per outcome so the frontend can localize the label.
        events.append(
            _Event(
                kind=f"proposal_{proposal.status}",
                at=proposal.resolved_at,
                actor_id=proposal.resolved_by,
                concept_id=proposal.concept_id,
                summary=proposal.title,
                version_id=_proposal_branch_head_id(proposal),
            )
        )

    events.sort(key=lambda e: e.at, reverse=True)
    return events[:limit]


def _proposal_branch_head_id(proposal: ChangeProposal) -> str | None:
    """Version subject of a proposal event: its source branch's current head
    (2026-07 correction to §4) — null if the branch was somehow removed."""
    branch = proposal.source_branch
    return branch.head_version_id if branch is not None else None


def _events_out(db: Session, events: list[_Event]) -> list[schemas.ActivityItemOut]:
    actor_ids = {e.actor_id for e in events if e.actor_id}
    actors = (
        {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}
        if actor_ids
        else {}
    )
    concept_ids = {e.concept_id for e in events}
    heads: dict[str, str] = {}
    if concept_ids:
        rows = (
            db.query(Concept.id, Version.canonical_form)
            .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
            .join(Version, Version.id == Branch.head_version_id)
            .filter(Concept.id.in_(concept_ids))
            .all()
        )
        heads = dict(rows)
    return [
        schemas.ActivityItemOut(
            kind=e.kind,
            at=e.at,
            actor=user_out(actors.get(e.actor_id) if e.actor_id else None),
            concept_id=e.concept_id,
            canonical_form=heads.get(e.concept_id, "?"),
            summary=e.summary,
            version_id=e.version_id,
        )
        for e in events
    ]


def count_events(db: Session, concept_ids: list[str], *, since: datetime | None = None) -> int:
    """Total row count across the same activity sources as `_collect_events`
    (versions, endorsements, comments, proposals opened, proposals resolved),
    without the per-source `limit` truncation — used for the concept page's
    `activity_count` (since=None, one concept) and the header bell's
    `/activity/unseen-count` (since=activity_seen_at, the caller's watched
    concepts)."""
    if not concept_ids:
        return 0

    def _after(query: OrmQuery[Any], column: InstrumentedAttribute[Any]) -> OrmQuery[Any]:
        return query.filter(column > since) if since is not None else query

    total: int = _after(
        db.query(Version).filter(Version.concept_id.in_(concept_ids)), Version.created_at
    ).count()
    total += _after(
        db.query(Endorsement)
        .join(Version, Version.id == Endorsement.version_id)
        .filter(Version.concept_id.in_(concept_ids)),
        Endorsement.created_at,
    ).count()
    total += _after(
        db.query(Comment).filter(Comment.concept_id.in_(concept_ids)), Comment.created_at
    ).count()
    total += _after(
        db.query(ChangeProposal).filter(ChangeProposal.concept_id.in_(concept_ids)),
        ChangeProposal.created_at,
    ).count()
    total += _after(
        db.query(ChangeProposal).filter(
            ChangeProposal.concept_id.in_(concept_ids),
            ChangeProposal.resolved_at.isnot(None),
        ),
        ChangeProposal.resolved_at,
    ).count()
    return total


def _watched_visible_concept_ids(db: Session, user: User) -> list[str]:
    watched = db.query(Watch).filter(Watch.user_id == user.id).all()
    return [
        w.concept_id
        for w in watched
        if (concept := db.get(Concept, w.concept_id)) is not None
        and can_view_collection(user, concept.collection)
    ]


@router.get("/concepts/{concept_id}/activity", response_model=list[schemas.ActivityItemOut])
def concept_activity(
    concept_id: str,
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.ActivityItemOut]:
    """Public, visibility-filtered: everything that happened to one concept."""
    concept = _get_visible_concept(db, concept_id, user)
    return _events_out(db, _collect_events(db, [concept.id], limit))


@router.get("/activity", response_model=list[schemas.ActivityItemOut])
def my_activity(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[schemas.ActivityItemOut]:
    """The personal feed: events across the caller's watched concepts only."""
    concept_ids = _watched_visible_concept_ids(db, user)
    if not concept_ids:
        return []
    return _events_out(db, _collect_events(db, concept_ids, limit))


# ── Header bell: unseen-activity count + read receipt ──


@router.get("/activity/unseen-count", response_model=schemas.UnseenCountOut)
def unseen_activity_count(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.UnseenCountOut:
    """Events across the caller's watched concepts newer than
    `activity_seen_at` (NULL ⇒ everything counts)."""
    concept_ids = _watched_visible_concept_ids(db, user)
    count = count_events(db, concept_ids, since=user.activity_seen_at)
    return schemas.UnseenCountOut(count=count)


@router.post("/activity/seen", status_code=204)
def mark_activity_seen(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """Stamp `activity_seen_at = now()` — clears the header bell's badge."""
    user.activity_seen_at = utcnow()
    db.commit()
