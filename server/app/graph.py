"""Version-graph service: the narrow bespoke core (VISION §4.1).

All version creation flows through here. Invariants enforced:
- versions are immutable (no update path exists anywhere),
- edges are only created together with a brand-new child → acyclic by construction,
- every concept has a 'main' branch; each branch has exactly one head,
- 'revise' requires the base to be a branch head (branch-and-reconcile, §4.5).
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .annotations import remap_annotations
from .errors import api_error
from .models import Branch, Concept, Version, VersionEdge


def coerce_status(status: str) -> str:
    """The status vocabulary is the TEXT's own lifecycle: draft → proposed →
    (deprecated | superseded). 'Fastställd' is NOT a status — it is an
    organisation's withdrawable endorsement of one specific version (see
    routers/endorsements.py, rework 2026-07-11). Legacy 'endorsed' payloads
    (old clients, imports, pre-migration rows copied by promote) coerce to
    'proposed'. Applied at every Version creation point."""
    return "proposed" if status == "endorsed" else status


def _branch_headed_by(db: Session, version_id: str) -> Branch | None:
    return db.query(Branch).filter(Branch.head_version_id == version_id).first()


def _get_version(db: Session, version_id: str, concept_id: str | None = None) -> Version:
    version = db.get(Version, version_id)
    if version is None or (concept_id is not None and version.concept_id != concept_id):
        raise api_error(
            404, "version_not_found", f"Version {version_id} not found", version_id=version_id
        )
    return version


def create_concept(
    db: Session,
    *,
    collection_id: str,
    canonical_form: str,
    language: str = "sv",
    definition_md: str = "",
    status: str = "draft",
    tags: list[str] | None = None,
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
    translated_from_version_id: str | None = None,
    spawned_from_id: str | None = None,
) -> tuple[Concept, Version, Branch]:
    """Create a concept with its initial version and main branch."""
    concept = Concept(
        collection_id=collection_id, created_by=created_by, spawned_from_id=spawned_from_id
    )
    if created_at is not None:
        concept.created_at = created_at
    db.add(concept)
    db.flush()

    branch = Branch(concept_id=concept.id, name="main")
    db.add(branch)
    db.flush()

    version = Version(
        concept_id=concept.id,
        branch_id=branch.id,
        language=language,
        canonical_form=canonical_form,
        definition_md=definition_md,
        status=coerce_status(status),
        tags=tags or [],
        note=note,
        provenance=provenance or {"kind": "human"},
        created_by=created_by,
    )
    if created_at is not None:
        version.created_at = created_at
    db.add(version)
    db.flush()

    if translated_from_version_id:
        source = _get_version(db, translated_from_version_id)
        db.add(
            VersionEdge(
                child_id=version.id,
                parent_id=source.id,
                edge_type="translated_from",
                note=note,
            )
        )

    branch.head_version_id = version.id
    db.flush()
    return concept, version, branch


def add_version(
    db: Session,
    *,
    concept: Concept,
    mode: str,
    base_version_id: str,
    canonical_form: str,
    definition_md: str,
    language: str | None = None,
    status: str = "draft",
    tags: list[str] | None = None,
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
    branch_name: str | None = None,
    extra_parent_ids: list[str] | None = None,
    source_version_id: str | None = None,
) -> Version:
    """Append a new immutable version. mode: revise | branch | synthesize | translate."""
    base = _get_version(db, base_version_id, concept_id=concept.id)

    if mode in ("revise", "synthesize"):
        branch = _branch_headed_by(db, base.id)
        if branch is None or branch.concept_id != concept.id:
            raise api_error(
                409,
                "base_not_head",
                "Base version is not a branch head. Someone else has moved this "
                "concept forward — create a branch and reconcile explicitly.",
            )
    elif mode == "branch":
        if not branch_name:
            raise api_error(
                422, "branch_name_required", "branch_name is required for mode=branch"
            )
        exists = (
            db.query(Branch)
            .filter(Branch.concept_id == concept.id, Branch.name == branch_name)
            .first()
        )
        if exists is not None:
            raise api_error(
                409,
                "branch_exists",
                f"Branch '{branch_name}' already exists",
                branch_name=branch_name,
            )
        branch = Branch(concept_id=concept.id, name=branch_name)
        db.add(branch)
        db.flush()
    elif mode == "translate":
        branch = _branch_headed_by(db, base.id)
        if branch is None:
            raise api_error(409, "base_not_head", "Base version is not a branch head")
        if not source_version_id:
            raise api_error(
                422, "source_version_required", "source_version_id is required for mode=translate"
            )
    else:
        raise api_error(422, "unknown_mode", f"Unknown mode '{mode}'", mode=mode)

    version = Version(
        concept_id=concept.id,
        branch_id=branch.id,
        language=language or base.language,
        canonical_form=canonical_form,
        definition_md=definition_md,
        status=coerce_status(status),
        tags=tags if tags is not None else list(base.tags or []),
        note=note,
        provenance=provenance or {"kind": "human"},
        created_by=created_by,
    )
    if created_at is not None:
        version.created_at = created_at
    db.add(version)
    db.flush()

    primary_edge_type = {
        "revise": "revised_from",
        "branch": "branched_from",
        "synthesize": "synthesized_from",
        "translate": "revised_from",
    }[mode]
    db.add(
        VersionEdge(
            child_id=version.id, parent_id=base.id, edge_type=primary_edge_type, ordinal=0
        )
    )

    if mode == "synthesize":
        # Dedupe against the base and repeats — synthesizing X with X is just a
        # revision of X, and a duplicate edge would violate uq_edge (500).
        seen_parents = {base.id}
        ordinal = 0
        for parent_id in extra_parent_ids or []:
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)
            parent = _get_version(db, parent_id)
            ordinal += 1
            db.add(
                VersionEdge(
                    child_id=version.id,
                    parent_id=parent.id,
                    edge_type="synthesized_from",
                    ordinal=ordinal,
                )
            )
    if mode == "translate":
        source = _get_version(db, source_version_id or "")
        db.add(
            VersionEdge(
                child_id=version.id, parent_id=source.id, edge_type="translated_from", ordinal=1
            )
        )

    # Paket A: section/author annotations survive the edit — remapped from
    # the same-lineage base (never from a cross-language translate source).
    remap_annotations(db, parent=base, child=version)

    branch.head_version_id = version.id
    db.flush()
    return version


def promote(
    db: Session,
    *,
    concept: Concept,
    version_id: str,
    note: str | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
    branch_name: str = "main",
    canonical_form: str | None = None,
    definition_md: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
) -> Version:
    """Restore an old version as the new head: copy content, keep history intact.

    The optional content overrides are the "edit a historical version" flow —
    the new head starts from the old version's content but may carry edits.
    Lineage is identical either way: promoted_from the old version plus
    revised_from the previous head. An explicit `status` is the editor's
    active choice; otherwise the successor rule applies (endorsed never
    carries over automatically)."""
    old = _get_version(db, version_id, concept_id=concept.id)
    branch = (
        db.query(Branch)
        .filter(Branch.concept_id == concept.id, Branch.name == branch_name)
        .first()
    )
    if branch is None:
        raise api_error(
            404, "branch_not_found", f"Branch '{branch_name}' not found", branch_name=branch_name
        )
    if branch.head_version_id == old.id:
        raise api_error(409, "version_already_head", "Version is already the head")

    version = Version(
        concept_id=concept.id,
        branch_id=branch.id,
        language=old.language,
        canonical_form=canonical_form if canonical_form is not None else old.canonical_form,
        definition_md=definition_md if definition_md is not None else old.definition_md,
        status=coerce_status(status if status is not None else old.status),
        tags=list(tags) if tags is not None else list(old.tags or []),
        note=note or f"Promoted version from {old.created_at:%Y-%m-%d}",
        provenance={"kind": "human", "promoted_from": old.id},
        created_by=created_by,
    )
    if created_at is not None:
        version.created_at = created_at
    db.add(version)
    db.flush()
    db.add(
        VersionEdge(child_id=version.id, parent_id=old.id, edge_type="promoted_from", ordinal=0)
    )
    # Also link to the previous head so lineage stays connected.
    if branch.head_version_id and branch.head_version_id != old.id:
        db.add(
            VersionEdge(
                child_id=version.id,
                parent_id=branch.head_version_id,
                edge_type="revised_from",
                ordinal=1,
            )
        )
    # Paket A: the promoted content comes from `old` — its annotations
    # follow the content (possibly shrunk by the editor's inline changes).
    remap_annotations(db, parent=old, child=version)

    branch.head_version_id = version.id
    db.flush()
    return version


def head_of(db: Session, concept: Concept, branch_name: str = "main") -> Version | None:
    branch = next((b for b in concept.branches if b.name == branch_name), None)
    if branch is None or branch.head_version_id is None:
        return None
    return db.get(Version, branch.head_version_id)
