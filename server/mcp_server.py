"""Kollepedia NG MCP server (FastMCP over stdio) — LOCAL DEVELOPMENT ONLY.

Exposes the concept graph to MCP clients (Claude Code, Claude Desktop, …) by
reusing the SQLAlchemy session and the graph service directly — no HTTP hop,
and writes under a handle-only "author" with no authentication. Never expose
it beyond a developer's machine: the hosted, read-only endpoint is
app/mcp_public.py at https://<host>/mcp.

Register with:
    claude mcp add kollepedia-dev -- uv --directory <abs>/server run python mcp_server.py
Run from server so `app` is importable (the `--directory` flag handles it).
"""

from typing import Any

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import graph
from app.db import SessionLocal
from app.models import Branch, Collection, Concept, User, Version, VersionEdge

mcp = FastMCP("kollepedia")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _resolve_author(db: Session, author: str) -> User:
    """Resolve or create a user by handle (mirrors app.deps.current_user)."""
    raw = (author or "mcp").strip() or "mcp"
    handle = raw.lower().replace(" ", "-")
    user = db.query(User).filter(User.handle == handle).first()
    if user is None:
        user = User(handle=handle, display_name=raw)
        db.add(user)
        db.flush()
    return user


def _get_concept(db: Session, concept_id: str) -> Concept:
    concept = db.get(Concept, concept_id)
    if concept is None:
        raise ValueError(f"Concept {concept_id} not found")
    return concept


def _ensure_writable(collection: Collection) -> None:
    """Night-3 lock/archive parity: the MCP author is an unprivileged dev
    identity, so locked and archived collections both refuse writes here."""
    if collection.is_archived:
        raise ValueError("Samlingen är arkiverad — avarkivera den för att kunna göra ändringar.")
    if collection.is_locked:
        raise ValueError(
            "Samlingen är låst — endast den ägande organisationens administratörer "
            "eller superadministratörer kan redigera (via API:t)."
        )


def _version_count(db: Session, concept_id: str) -> int:
    return db.query(func.count(Version.id)).filter(Version.concept_id == concept_id).scalar() or 0


def _concept_summary(db: Session, concept: Concept, head: Version | None) -> dict[str, Any]:
    return {
        "id": concept.id,
        "canonical_form": head.canonical_form if head else None,
        "definition": head.definition_md if head else None,
        "language": head.language if head else None,
        "status": head.status if head else None,
        "collection_slug": concept.collection.slug,
        "version_count": _version_count(db, concept.id),
    }


def _snippet(text: str, length: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool()
def list_collections() -> list[dict[str, Any]]:
    """List all terminology collections with concept counts."""
    with SessionLocal() as db:
        counts = dict(
            db.query(Concept.collection_id, func.count(Concept.id))
            .group_by(Concept.collection_id)
            .all()
        )
        collections = db.query(Collection).order_by(Collection.year.asc().nulls_last()).all()
        return [
            {
                "slug": c.slug,
                "name": c.name,
                "year": c.year,
                "authoritative": c.authoritative,
                "concept_count": counts.get(c.id, 0),
            }
            for c in collections
        ]


@mcp.tool()
def search_concepts(
    q: str, collection: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Search concepts by term or definition text (head versions).

    `collection` filters by collection slug; `limit` caps the result count.
    """
    limit = max(1, min(limit, 100))
    with SessionLocal() as db:
        query = (
            db.query(Concept, Version, Collection)
            .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
            .join(Version, Version.id == Branch.head_version_id)
            .join(Collection, Collection.id == Concept.collection_id)
        )
        if collection:
            query = query.filter(Collection.slug == collection)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(Version.canonical_form.ilike(like), Version.definition_md.ilike(like))
            )
        rows = query.order_by(Version.canonical_form.asc()).limit(limit).all()
        return [
            {
                "id": concept.id,
                "canonical_form": head.canonical_form,
                "definition": _snippet(head.definition_md),
                "language": head.language,
                "status": head.status,
                "collection_slug": coll.slug,
            }
            for concept, head, coll in rows
        ]


@mcp.tool()
def get_concept(concept_id: str) -> dict[str, Any]:
    """Get a concept's current head version, branches and version count."""
    with SessionLocal() as db:
        concept = _get_concept(db, concept_id)
        head = graph.head_of(db, concept)
        summary = _concept_summary(db, concept, head)
        summary["head_version_id"] = head.id if head else None
        summary["branches"] = [
            {"name": b.name, "head_version_id": b.head_version_id} for b in concept.branches
        ]
        return summary


@mcp.tool()
def get_concept_graph(concept_id: str) -> dict[str, Any]:
    """Get a concept's full version DAG: versions, edges and branches (trimmed)."""
    with SessionLocal() as db:
        concept = _get_concept(db, concept_id)
        versions = (
            db.query(Version)
            .filter(Version.concept_id == concept.id)
            .order_by(Version.created_at.asc())
            .all()
        )
        version_ids = [v.id for v in versions]
        edges = (
            db.query(VersionEdge).filter(VersionEdge.child_id.in_(version_ids)).all()
            if version_ids
            else []
        )
        return {
            "concept_id": concept.id,
            "collection_slug": concept.collection.slug,
            "versions": [
                {
                    "id": v.id,
                    "canonical_form": v.canonical_form,
                    "definition": v.definition_md,
                    "language": v.language,
                    "status": v.status,
                    "note": v.note,
                    "tags": list(v.tags or []),
                    "created_at": v.created_at.isoformat(),
                    "branch_id": v.branch_id,
                }
                for v in versions
            ],
            "edges": [
                {
                    "child_id": e.child_id,
                    "parent_id": e.parent_id,
                    "edge_type": e.edge_type,
                    "ordinal": e.ordinal,
                }
                for e in edges
            ],
            "branches": [
                {"id": b.id, "name": b.name, "head_version_id": b.head_version_id}
                for b in concept.branches
            ],
        }


@mcp.tool()
def create_concept(
    collection_slug: str,
    canonical_form: str,
    definition_md: str,
    language: str = "sv",
    note: str | None = None,
    author: str = "mcp",
) -> dict[str, Any]:
    """Create a new concept (with its initial version and main branch)."""
    with SessionLocal() as db:
        collection = db.query(Collection).filter(Collection.slug == collection_slug).first()
        if collection is None:
            raise ValueError(f"Collection '{collection_slug}' not found")
        _ensure_writable(collection)
        user = _resolve_author(db, author)
        concept, version, branch = graph.create_concept(
            db,
            collection_id=collection.id,
            canonical_form=canonical_form,
            language=language,
            definition_md=definition_md,
            note=note,
            provenance={"kind": "llm", "provider": "mcp"},
            created_by=user.id,
        )
        db.commit()
        return {
            "concept_id": concept.id,
            "version_id": version.id,
            "branch": branch.name,
            "canonical_form": version.canonical_form,
            "collection_slug": collection.slug,
        }


@mcp.tool()
def add_version(
    concept_id: str,
    mode: str,
    base_version_id: str,
    canonical_form: str,
    definition_md: str,
    note: str | None = None,
    author: str = "mcp",
    branch_name: str | None = None,
) -> dict[str, Any]:
    """Append a new version to a concept. mode: revise | branch | synthesize.

    'revise' requires base_version_id to be a branch head (else the tool
    errors and you should branch instead); 'branch' requires branch_name.
    """
    with SessionLocal() as db:
        concept = _get_concept(db, concept_id)
        _ensure_writable(concept.collection)
        user = _resolve_author(db, author)
        try:
            version = graph.add_version(
                db,
                concept=concept,
                mode=mode,
                base_version_id=base_version_id,
                canonical_form=canonical_form,
                definition_md=definition_md,
                note=note,
                provenance={"kind": "llm", "provider": "mcp"},
                created_by=user.id,
                branch_name=branch_name,
            )
        except HTTPException as exc:  # graph service speaks HTTP; translate for MCP
            raise ValueError(exc.detail) from None
        db.commit()
        return {
            "version_id": version.id,
            "concept_id": concept.id,
            "branch_id": version.branch_id,
            "mode": mode,
            "canonical_form": version.canonical_form,
            "status": version.status,
        }


if __name__ == "__main__":
    mcp.run()
