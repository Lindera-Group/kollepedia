"""Exports — collections and pinned lists as CSV / Markdown / JSON-LD / SKOS / TBX.

VISION §8.3: standards from the first schema draft. The serializers here are
pragmatic but valid: SKOS Turtle with language-tagged literals, TBX-Core
(`martif`) with one termEntry per concept and one langSet per language, and
JSON-LD with a skos/prov/dct context. Lists export their *pinned* versions
(or the current head for follow_head items) — a pin must survive later head
movement (VISION §9.2).
"""

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import can_view_collection, current_user, export_allowed, require_user
from ..errors import api_error
from ..models import (
    Branch,
    Collection,
    Concept,
    ConceptRelation,
    PinList,
    User,
    Version,
    VersionEdge,
)
from .lists import _resolve_version

router = APIRouter(tags=["exports"])


# --------------------------------------------------------------------------
# Export bundle assembly
# --------------------------------------------------------------------------


@dataclass
class ExportEntry:
    concept_id: str
    version_id: str
    canonical_form: str
    language: str
    definition_md: str
    status: str
    tags: list[str]
    collection_slug: str
    created_at: datetime
    author: str
    # None → collection export; True/False → list item follow_head flag.
    follow_head: bool | None = None
    # translated_from-linked versions in other languages: (language, form).
    translations: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ExportBundle:
    title: str
    subtitle: str | None
    filename_stem: str
    entries: list[ExportEntry]
    # (from_concept_id, to_concept_id, relation_type) — both ends exported.
    relations: list[tuple[str, str, str]]


def _slugify(text: str) -> str:
    text = text.lower().replace("å", "a").replace("ä", "a").replace("ö", "o").replace("é", "e")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _authors_for(db: Session, versions: list[Version]) -> dict[str, str]:
    user_ids = {v.created_by for v in versions if v.created_by}
    if not user_ids:
        return {}
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    return {u.id: u.display_name for u in users}


def _translations_map(
    db: Session, concept_ids: list[str], language_by_concept: dict[str, str]
) -> dict[str, list[tuple[str, str]]]:
    """Per exported concept: (language, canonical_form) of translated_from-linked
    versions that live on *other* concepts in *other* languages."""
    if not concept_ids:
        return {}
    rows = (
        db.query(Version.id, Version.concept_id).filter(Version.concept_id.in_(concept_ids)).all()
    )
    concept_by_version = {version_id: concept_id for version_id, concept_id in rows}
    if not concept_by_version:
        return {}
    local_ids = list(concept_by_version)
    edges = (
        db.query(VersionEdge)
        .filter(
            VersionEdge.edge_type == "translated_from",
            or_(VersionEdge.child_id.in_(local_ids), VersionEdge.parent_id.in_(local_ids)),
        )
        .all()
    )
    linked_ids = {e.child_id for e in edges} | {e.parent_id for e in edges}
    linked = (
        {v.id: v for v in db.query(Version).filter(Version.id.in_(list(linked_ids))).all()}
        if linked_ids
        else {}
    )
    out: dict[str, list[tuple[str, str]]] = {}
    seen: dict[str, set[tuple[str, str]]] = {}
    for edge in edges:
        ends = ((edge.child_id, edge.parent_id), (edge.parent_id, edge.child_id))
        for local_id, other_id in ends:
            concept_id = concept_by_version.get(local_id)
            other = linked.get(other_id)
            if concept_id is None or other is None or other.concept_id == concept_id:
                continue
            if other.language == language_by_concept.get(concept_id):
                continue
            pair = (other.language, other.canonical_form)
            if pair in seen.setdefault(concept_id, set()):
                continue
            seen[concept_id].add(pair)
            out.setdefault(concept_id, []).append(pair)
    return out


def _relations_for(db: Session, concept_ids: list[str]) -> list[tuple[str, str, str]]:
    """Relations where both ends are in the exported set."""
    if not concept_ids:
        return []
    rows = (
        db.query(ConceptRelation)
        .filter(
            ConceptRelation.from_concept_id.in_(concept_ids),
            ConceptRelation.to_concept_id.in_(concept_ids),
        )
        .all()
    )
    return [(r.from_concept_id, r.to_concept_id, r.relation_type) for r in rows]


def _collection_bundle(db: Session, slug: str) -> ExportBundle:
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if collection is None:
        raise api_error(404, "collection_not_found", "Collection not found")
    rows = (
        db.query(Concept, Version)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .filter(Concept.collection_id == collection.id)
        .order_by(Version.canonical_form.asc())
        .all()
    )
    authors = _authors_for(db, [v for _, v in rows])
    concept_ids = [c.id for c, _ in rows]
    languages = {c.id: v.language for c, v in rows}
    translations = _translations_map(db, concept_ids, languages)
    entries = [
        ExportEntry(
            concept_id=concept.id,
            version_id=head.id,
            canonical_form=head.canonical_form,
            language=head.language,
            definition_md=head.definition_md,
            status=head.status,
            tags=list(head.tags or []),
            collection_slug=collection.slug,
            created_at=head.created_at,
            author=authors.get(head.created_by or "", ""),
            translations=translations.get(concept.id, []),
        )
        for concept, head in rows
    ]
    return ExportBundle(
        title=collection.name,
        subtitle=collection.description,
        filename_stem=collection.slug,
        entries=entries,
        relations=_relations_for(db, concept_ids),
    )


def _list_bundle(db: Session, list_id: str) -> ExportBundle:
    pin_list = db.get(PinList, list_id)
    if pin_list is None:
        raise api_error(404, "list_not_found", "List not found")
    resolved: list[tuple] = []
    for item in sorted(pin_list.items, key=lambda i: i.ordinal):
        version = _resolve_version(db, item)
        # A pinned version must belong to the item's concept; anything else is
        # a stale or forged pin and is not exported.
        if version is not None and version.concept_id == item.concept_id:
            resolved.append((item, version))
    concept_ids = [version.concept_id for _, version in resolved]
    concepts = (
        {c.id: c for c in db.query(Concept).filter(Concept.id.in_(concept_ids)).all()}
        if concept_ids
        else {}
    )
    collection_ids = {c.collection_id for c in concepts.values()}
    collections = (
        {c.id: c for c in db.query(Collection).filter(Collection.id.in_(list(collection_ids)))}
        if collection_ids
        else {}
    )
    # Concepts from collections whose licence forbids redistribution are left
    # out of the file (same rule as the collection export); the subtitle says so.
    blocked_collections = {cid for cid, c in collections.items() if not export_allowed(c)}
    omitted = 0
    if blocked_collections:
        kept = []
        for item, version in resolved:
            concept = concepts.get(version.concept_id)
            if concept is None or concept.collection_id in blocked_collections:
                omitted += 1
            else:
                kept.append((item, version))
        resolved = kept
        concept_ids = [version.concept_id for _, version in resolved]
    authors = _authors_for(db, [v for _, v in resolved])
    languages = {item.concept_id: v.language for item, v in resolved}
    translations = _translations_map(db, concept_ids, languages)
    entries = []
    for item, version in resolved:
        concept = concepts.get(item.concept_id)
        collection = collections.get(concept.collection_id) if concept else None
        entries.append(
            ExportEntry(
                concept_id=item.concept_id,
                version_id=version.id,
                canonical_form=version.canonical_form,
                language=version.language,
                definition_md=version.definition_md,
                status=version.status,
                tags=list(version.tags or []),
                collection_slug=collection.slug if collection else "",
                created_at=version.created_at,
                author=authors.get(version.created_by or "", ""),
                follow_head=item.follow_head,
                translations=translations.get(item.concept_id, []),
            )
        )
    subtitle = pin_list.purpose
    if omitted:
        note = (
            f"{omitted} begrepp utelämnade – licensen tillåter inte vidarespridning / "
            f"{omitted} concepts omitted – licence does not permit redistribution"
        )
        subtitle = f"{subtitle} ({note})" if subtitle else note
    return ExportBundle(
        title=pin_list.name,
        subtitle=subtitle,
        filename_stem=_slugify(pin_list.name) or f"list-{pin_list.id[:8]}",
        entries=entries,
        relations=_relations_for(db, concept_ids),
    )


# --------------------------------------------------------------------------
# Format serializers
# --------------------------------------------------------------------------

URN_PREFIX = "urn:kollepedia:concept:"

RELATION_TO_SKOS = {
    "related_to": "skos:related",
    "broader": "skos:broader",
    "narrower": "skos:narrower",
    "exact_match": "skos:exactMatch",
    "close_match": "skos:closeMatch",
}

JSONLD_CONTEXT = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "prov": "http://www.w3.org/ns/prov#",
    "dct": "http://purl.org/dc/terms/",
}


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _ttl_escape(text: str) -> str:
    """Escape a string for a single-quoted Turtle literal ("…")."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _to_csv(bundle: ExportBundle) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "canonical_form",
            "language",
            "definition",
            "status",
            "tags",
            "collection",
            "version_id",
            "version_date",
            "author",
        ]
    )
    for e in bundle.entries:
        writer.writerow(
            [
                e.canonical_form,
                e.language,
                e.definition_md,
                e.status,
                ";".join(e.tags),
                e.collection_slug,
                e.version_id,
                f"{e.created_at:%Y-%m-%d}",
                e.author,
            ]
        )
    return buffer.getvalue()


def _to_markdown(bundle: ExportBundle) -> str:
    lines = [f"# {bundle.title}", ""]
    if bundle.subtitle:
        lines += [f"> {bundle.subtitle}", ""]
    for e in bundle.entries:
        if e.follow_head is None:
            pin_kind = f"{e.created_at:%Y-%m-%d}"
        elif e.follow_head:
            pin_kind = "follows head"
        else:
            pin_kind = f"pinned {e.created_at:%Y-%m-%d}"
        lines += [
            f"## {e.canonical_form}",
            "",
            e.definition_md,
            "",
            f"*Version `{e.version_id[:8]}` ({pin_kind}), status: {e.status}.*",
            "",
        ]
    return "\n".join(lines)


def _to_jsonld(bundle: ExportBundle) -> str:
    nodes = []
    for e in bundle.entries:
        node: dict = {
            "@id": f"{URN_PREFIX}{e.concept_id}",
            "@type": "skos:Concept",
            "skos:prefLabel": {"@value": e.canonical_form, "@language": e.language},
            "skos:definition": {"@value": e.definition_md, "@language": e.language},
            "dct:created": f"{e.created_at:%Y-%m-%d}",
        }
        if e.author:
            node["prov:wasAttributedTo"] = e.author
        nodes.append(node)
    return json.dumps({"@context": JSONLD_CONTEXT, "@graph": nodes}, ensure_ascii=False, indent=2)


def _to_skos(bundle: ExportBundle) -> str:
    lines = [
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix skosxl: <http://www.w3.org/2008/05/skos-xl#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    exported = {e.concept_id for e in bundle.entries}
    relations_by_from: dict[str, list[tuple[str, str]]] = {}
    for from_id, to_id, relation_type in bundle.relations:
        prop = RELATION_TO_SKOS.get(relation_type)
        if prop and from_id in exported and to_id in exported:
            relations_by_from.setdefault(from_id, []).append((prop, to_id))
    for e in bundle.entries:
        triples = [
            f"<{URN_PREFIX}{e.concept_id}> a skos:Concept",
            f'    skos:prefLabel "{_ttl_escape(e.canonical_form)}"@{e.language}',
        ]
        if e.definition_md:
            triples.append(f'    skos:definition "{_ttl_escape(e.definition_md)}"@{e.language}')
        triples.append(f'    dct:created "{e.created_at:%Y-%m-%d}"^^xsd:date')
        if e.author:
            triples.append(f'    prov:wasAttributedTo "{_ttl_escape(e.author)}"')
        for prop, to_id in relations_by_from.get(e.concept_id, []):
            triples.append(f"    {prop} <{URN_PREFIX}{to_id}>")
        lines.append(" ;\n".join(triples) + " .")
        lines.append("")
    return "\n".join(lines)


def _to_tbx(bundle: ExportBundle) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<martif type="TBX" xml:lang="sv">',
        "  <martifHeader>",
        "    <fileDesc>",
        f"      <titleStmt><title>{_xml_escape(bundle.title)}</title></titleStmt>",
        "      <sourceDesc><p>Kollepedia NG export</p></sourceDesc>",
        "    </fileDesc>",
        "  </martifHeader>",
        "  <text>",
        "    <body>",
    ]
    seen: dict[str, int] = {}
    for e in bundle.entries:
        repeat = seen.get(e.concept_id, 0)
        seen[e.concept_id] = repeat + 1
        entry_id = f"c-{e.concept_id}" if repeat == 0 else f"c-{e.concept_id}-{repeat}"
        lines.append(f'      <termEntry id="{entry_id}">')
        if e.definition_md:
            lines.append(
                f'        <descrip type="definition">{_xml_escape(e.definition_md)}</descrip>'
            )
        lang_sets = [(e.language, e.canonical_form), *e.translations]
        for language, form in lang_sets:
            lines += [
                f'        <langSet xml:lang="{_xml_escape(language)}">',
                f"          <tig><term>{_xml_escape(form)}</term></tig>",
                "        </langSet>",
            ]
        lines.append("      </termEntry>")
    lines += ["    </body>", "  </text>", "</martif>", ""]
    return "\n".join(lines)


FORMATS = {
    "csv": ("text/csv", "csv", _to_csv),
    "markdown": ("text/markdown", "md", _to_markdown),
    "jsonld": ("application/ld+json", "jsonld", _to_jsonld),
    "skos": ("text/turtle", "ttl", _to_skos),
    "tbx": ("application/xml", "tbx", _to_tbx),
}


def _render(bundle: ExportBundle, format: str) -> Response:
    if format not in FORMATS:
        raise api_error(
            422,
            "export_format_unknown",
            f"Unknown format '{format}': allowed {sorted(FORMATS)}",
            format=format,
            allowed=", ".join(sorted(FORMATS)),
        )
    media_type, extension, serializer = FORMATS[format]
    filename = f"{bundle.filename_stem}.{extension}"
    return Response(
        content=serializer(bundle),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get("/collections/{slug}/export")
def export_collection(
    slug: str,
    format: str = "csv",
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    """Export a collection's head versions (VISION §8.3)."""
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if collection is None or not can_view_collection(user, collection):
        raise api_error(404, "collection_not_found", "Collection not found")
    if not export_allowed(collection):
        licence = (collection.licence or {}).get("label") or ""
        raise api_error(
            403,
            "export_not_permitted",
            "This collection is published by permission and its licence does not "
            "permit redistribution — read it on the site, but it cannot be exported.",
            licence=licence,
        )
    return _render(_collection_bundle(db, slug), format)


@router.get("/lists/{list_id}/export")
def export_list(
    list_id: str,
    format: str = "markdown",
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Response:
    """Export a list as a self-contained, pinned glossary (VISION §8.3, §9.2).
    Owner-only — the list is a private profile (säkerhetsfix 2026-07-15)."""
    pin_list = db.get(PinList, list_id)
    if pin_list is None or (pin_list.owner_id != user.id and not user.is_super_admin):
        raise api_error(404, "list_not_found", "List not found")
    return _render(_list_bundle(db, list_id), format)
