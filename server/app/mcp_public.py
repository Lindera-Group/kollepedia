"""Public MCP endpoint — read and search the public collections (MCP v1).

Mounted by app/main.py at ``/mcp`` (Streamable HTTP, stateless, JSON
responses), so any MCP client — Claude, Claude Code, Cursor, ChatGPT
connectors — can read Kollepedia without an account:

    claude mcp add --transport http kollepedia https://kollepedia.se/mcp

Everything here runs as an anonymous reader: the same visibility rule as the
public API (``visible_collection_criterion(None)`` / ``can_view_collection``),
no writes, and no bulk content for collections whose licence forbids
redistribution (they stay searchable; ``export_allowed`` says so). Logged-in
access with the user's own rights is MCP v2 (API keys as Bearer) and lives
outside this module. The stdio server in ``mcp_server.py`` is the local
development variant and is not exposed.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import graph, search
from .db import SessionLocal
from .deps import can_view_collection, export_allowed, visible_collection_criterion
from .models import Collection, Concept, ConceptRelation, Version

mcp = FastMCP(
    "kollepedia",
    instructions=(
        "Kollepedia är kollektivtrafikens gemensamma begreppsbank (svenska och "
        "engelska). Sök begrepp, läs definitioner med proveniens och versionshistorik, "
        "och se hur samlingar (Transmodel, NeTEx, SUTI, NOPTIS, Kollektivtrafikordboken …) "
        "relaterar. Allt här är publikt och skrivskyddat.\n\n"
        "Språk: varje begrepp har ett språk (language: sv eller en). Samma begrepp på "
        "ett annat språk är ett eget begrepp med egen definition, länkat som översättning "
        "(translations i sökträffar och i get_concept). Samma term kan finnas flera "
        "gånger i en samling med olika översättningar; då är det översättningen som "
        "skiljer betydelserna åt. Motsvarigheter mellan samlingar – till exempel mot "
        "Transmodel, som bara finns på engelska – står som relationer (exact_match, "
        "close_match, broader, related_to), och varje relation anger språket i andra "
        "änden. För att harmonisera ett begrepp mellan språk: sök termen, följ "
        "translations till motsvarigheten, och följ dess relationer eller sök dess "
        "term i målsamlingen (search_concepts med collection och language)."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    # The endpoint sits behind Traefik on known public hosts; the SDK's
    # localhost-oriented DNS-rebinding guard would otherwise reject them.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

PUBLIC_TOOLS = (
    "list_collections",
    "get_collection",
    "search_concepts",
    "get_concept",
    "get_concept_history",
)


def public_origin() -> str:
    """The site's public origin for links in tool results — the first entry of
    CORS_ORIGINS (set per environment in compose), else the dev frontend."""
    raw = os.getenv("CORS_ORIGINS", "").split(",")[0].strip()
    return raw or "http://localhost:5181"


def _snippet(text: str | None, length: int = 240) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _collection_out(db: Session, c: Collection, count: int) -> dict[str, Any]:
    licence = c.licence or {}
    out: dict[str, Any] = {
        "slug": c.slug,
        "name": c.name,
        "year": c.year,
        "authoritative": c.authoritative,
        "organisation": c.organisation.name if c.organisation else None,
        "concept_count": count,
        "licence": licence.get("label"),
        "export_allowed": export_allowed(c),
        "url": f"{public_origin()}/collections/{c.slug}",
    }
    if export_allowed(c):
        out["export_url"] = f"{public_origin()}/api/v1/collections/{c.slug}/export?format=csv"
    return out


def _public_concept(db: Session, concept_id: str) -> Concept:
    """A concept the anonymous reader may see. Prototype term ids, which the
    links in imported definitions carry, resolve as they do on the site."""
    concept = graph.find_concept(db, concept_id)
    if concept is None or not can_view_collection(None, concept.collection):
        raise ValueError(f"Begreppet {concept_id} finns inte.")
    return concept


def _head_out(concept: Concept, head: Version | None) -> dict[str, Any]:
    return {
        "id": concept.id,
        "canonical_form": head.canonical_form if head else None,
        "definition_md": head.definition_md if head else None,
        "language": head.language if head else None,
        "status": head.status if head else None,
        "tags": list(head.tags or []) if head else [],
        "collection_slug": concept.collection.slug,
        "url": f"{public_origin()}/concepts/{concept.id}",
    }


def _relations(db: Session, concept: Concept) -> list[dict[str, Any]]:
    rows = (
        db.query(ConceptRelation)
        .filter(
            or_(
                ConceptRelation.from_concept_id == concept.id,
                ConceptRelation.to_concept_id == concept.id,
            )
        )
        .all()
    )
    out: list[dict[str, Any]] = []
    for rel in rows:
        other_id = rel.to_concept_id if rel.from_concept_id == concept.id else rel.from_concept_id
        other = db.get(Concept, other_id)
        if other is None or not can_view_collection(None, other.collection):
            continue
        head = graph.head_of(db, other)
        out.append(
            {
                "relation_type": rel.relation_type,
                "direction": "out" if rel.from_concept_id == concept.id else "in",
                "concept_id": other.id,
                "canonical_form": head.canonical_form if head else None,
                "language": head.language if head else None,
                "collection_slug": other.collection.slug,
            }
        )
    return out


def _public_translations(
    db: Session, concept_ids: list[str]
) -> dict[str, list[tuple[Concept, Version]]]:
    """graph.translations_of, without the concepts the anonymous reader may
    not see."""
    return {
        concept_id: [
            (other, shown) for other, shown in found if can_view_collection(None, other.collection)
        ]
        for concept_id, found in graph.translations_of(db, concept_ids).items()
    }


# ── Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def list_collections() -> list[dict[str, Any]]:
    """List the public terminology collections with concept counts, licence and
    whether bulk export is allowed."""
    with SessionLocal() as db:
        counts = dict(
            db.query(Concept.collection_id, func.count(Concept.id))
            .group_by(Concept.collection_id)
            .all()
        )
        collections = (
            db.query(Collection)
            .filter(visible_collection_criterion(None), Collection.is_archived.is_(False))
            .order_by(Collection.year.asc().nulls_last(), Collection.name.asc())
            .all()
        )
        return [_collection_out(db, c, counts.get(c.id, 0)) for c in collections]


@mcp.tool()
def get_collection(slug: str) -> dict[str, Any]:
    """A public collection in detail: description, credits, source, licence."""
    with SessionLocal() as db:
        c = db.query(Collection).filter(Collection.slug == slug).first()
        if c is None or not can_view_collection(None, c):
            raise ValueError(f"Samlingen {slug!r} finns inte.")
        count = db.query(func.count(Concept.id)).filter(Concept.collection_id == c.id).scalar()
        out = _collection_out(db, c, count or 0)
        out.update(
            {
                "description": c.description,
                "credits": c.credits,
                "source_url": c.source_url,
                "archive_url": c.archive_url,
                "is_locked": c.is_locked,
            }
        )
        return out


@mcp.tool()
def search_concepts(
    q: str, collection: str | None = None, language: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Search public concepts by term or definition text (current head
    versions), in Swedish and English alike. Hits come in the same order as
    in the search field on the site: the exact term first, then terms that
    start with the query, terms that contain it, and last concepts where only
    the definition matches; alphabetical within each group. `collection`
    narrows to one collection slug (or several, comma-separated); `language`
    to concepts written in "sv" or "en"; `limit` ≤ 100.

    Each hit names its `translations`: the same concept in the other
    language, a concept of its own to read with get_concept. A term that
    comes back several times from one collection is one concept per meaning;
    the translations tell them apart."""
    limit = max(1, min(int(limit), 100))
    with SessionLocal() as db:
        # The matching and the order are the site's own (app/search.py).
        query = search.in_collections(search.head_query(db, None), collection)
        query = search.in_language(query, language)
        query, order = search.text_search(query, q)
        rows = query.order_by(*order).limit(limit).all()
        translations = _public_translations(db, [concept.id for concept, _, _ in rows])
        return [
            {
                "id": concept.id,
                "canonical_form": head.canonical_form,
                "definition": _snippet(head.definition_md),
                "language": head.language,
                "status": head.status,
                "collection_slug": coll.slug,
                "url": f"{public_origin()}/concepts/{concept.id}",
                "translations": [
                    {
                        "id": other.id,
                        "canonical_form": shown.canonical_form,
                        "language": shown.language,
                    }
                    for other, shown in translations.get(concept.id, [])
                ],
            }
            for concept, head, coll in rows
        ]


@mcp.tool()
def get_concept(concept_id: str) -> dict[str, Any]:
    """A public concept's current definition with tags, its translations,
    relations to other public concepts, and its version count.

    `translations` are the same concept in the other language, each with its
    own definition: what the term is called there and how it is defined.
    `relations` are typed links to other concepts (exact_match, close_match,
    broader, related_to), within and across collections; each gives the
    language of the concept at the other end."""
    with SessionLocal() as db:
        concept = _public_concept(db, concept_id)
        head = graph.head_of(db, concept)
        out = _head_out(concept, head)
        out["version_count"] = (
            db.query(func.count(Version.id)).filter(Version.concept_id == concept.id).scalar() or 0
        )
        out["translations"] = [
            {
                "id": other.id,
                "canonical_form": shown.canonical_form,
                "language": shown.language,
                "definition_md": shown.definition_md,
                "collection_slug": other.collection.slug,
                "url": f"{public_origin()}/concepts/{other.id}",
            }
            for other, shown in _public_translations(db, [concept.id]).get(concept.id, [])
        ]
        out["relations"] = _relations(db, concept)
        return out


@mcp.tool()
def get_concept_history(concept_id: str) -> dict[str, Any]:
    """A public concept's version history (oldest first): text, status, note
    and date per version, plus the branches."""
    with SessionLocal() as db:
        concept = _public_concept(db, concept_id)
        versions = (
            db.query(Version)
            .filter(Version.concept_id == concept.id)
            .order_by(Version.created_at.asc())
            .all()
        )
        return {
            "concept_id": concept.id,
            "collection_slug": concept.collection.slug,
            "url": f"{public_origin()}/concepts/{concept.id}/history",
            "branches": [
                {"name": b.name, "head_version_id": b.head_version_id} for b in concept.branches
            ],
            "versions": [
                {
                    "id": v.id,
                    "canonical_form": v.canonical_form,
                    "definition_md": v.definition_md,
                    "language": v.language,
                    "status": v.status,
                    "note": v.note,
                    "created_at": v.created_at.isoformat(),
                    "branch_id": v.branch_id,
                }
                for v in versions
            ],
        }


# Built once at import. streamable_http_app() creates the (lazy) session
# manager that the application lifespan drives; the bare ASGI handler is what
# main.py registers as an exact Route — a Mount would redirect /mcp to /mcp/,
# which MCP clients do not follow.
mcp.streamable_http_app()
asgi = StreamableHTTPASGIApp(mcp.session_manager)
