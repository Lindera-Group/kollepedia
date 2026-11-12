"""Pydantic schemas — the API contract shared with web/src/lib/api.ts.

Free-text fields on write schemas carry max lengths (2026-11-10): history is
immutable, so a megabyte posted into a definition could never be removed
again. The caps are generous for real terminology work (a 50 000-character
definition is a book chapter) and only exist to make abuse impossible.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

CANONICAL_FORM_MAX = 500  # matches the import pipeline's existing cap
DEFINITION_MAX = 50_000
NOTE_MAX = 5_000
DESCRIPTION_MAX = 10_000  # collection and proposal descriptions (router-local schemas)
BRANCH_NAME_MAX = 100
TAG_MAX = 100
TAGS_MAX = 50

CanonicalForm = Annotated[str, Field(max_length=CANONICAL_FORM_MAX)]
DefinitionMd = Annotated[str, Field(max_length=DEFINITION_MAX)]
Note = Annotated[str, Field(max_length=NOTE_MAX)]
BranchName = Annotated[str, Field(max_length=BRANCH_NAME_MAX)]
Tags = Annotated[list[Annotated[str, Field(max_length=TAG_MAX)]], Field(max_length=TAGS_MAX)]


class LicenceOut(BaseModel):
    label: str | None = None
    url: str | None = None
    odrl: dict[str, Any] | None = None


class CollectionOrgOut(BaseModel):
    id: str
    slug: str
    name: str


class ContributorOut(BaseModel):
    """Paket B: one row in the collection's author list — the living
    equivalent of the old Ordbok page's publication credit. Aggregated from
    version authorship and per-section author annotations."""

    handle: str
    display_name: str
    affiliation: str | None = None
    activated: bool = False
    version_count: int = 0
    section_count: int = 0


class CollectionOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    year: int | None = None
    authoritative: bool = False
    licence: dict[str, Any] | None = None
    concept_count: int = 0
    # Iteration 2: visibility + ownership; `editable` is computed for the caller.
    visibility: str = "public"
    organisation: CollectionOrgOut | None = None
    created_by: str | None = None
    editable: bool = False
    # can_write = can_edit (write versions here); editable = can_manage (admin).
    can_write: bool = False
    # Iteration 3: lock/archive state (VISION §4.3).
    is_locked: bool = False
    is_archived: bool = False
    # False when the licence forbids redistribution: no bulk export, read on site.
    export_allowed: bool = True
    # Iteration 4: who may write here — org | anyone | open.
    edit_policy: str = "anyone"
    # Rich metadata restored from the old site (migration 007). credits and the
    # two URLs are PATCH-editable; sources/locales are imported provenance.
    source_url: str | None = None
    archive_url: str | None = None
    credits: str | None = None
    sources: list[dict[str, Any]] | None = None
    locales: dict[str, Any] | None = None
    # Paket B: only populated on the detail endpoint (GET /collections/{slug});
    # None on list responses to keep them light.
    contributors: list[ContributorOut] | None = None


class UserOut(BaseModel):
    id: str
    handle: str
    display_name: str
    affiliation: str | None = None


class AnnotationOut(BaseModel):
    id: str
    attr_type: str
    start: int
    end: int
    quote: str | None = None
    value: dict[str, Any] = Field(default_factory=dict)
    # Paket A: {"kind": "remap", "from_version": …} on carried-forward rows.
    provenance: dict[str, Any] = Field(default_factory=dict)


class TagCountOut(BaseModel):
    name: str
    count: int


class TaxonomyValueOut(BaseModel):
    id: str
    # Bilingual (unlike tags): name = Swedish, name_en falls back to name.
    name: str
    name_en: str | None = None
    position: int


class TaxonomyOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    scope: str
    collection_id: str | None = None
    # min is SOFT (UI/import guidance); max is HARD when set (parts: 1).
    min_per_concept: int = 0
    max_per_concept: int | None = None
    values: list[TaxonomyValueOut] = Field(default_factory=list)


class ConceptTaxonomyOut(BaseModel):
    """One taxonomy's assigned values on a concept (assignment lives on the
    CONCEPT, not the version — recategorisation never mints text versions)."""

    taxonomy_id: str
    taxonomy_slug: str
    taxonomy_name: str
    scope: str
    max_per_concept: int | None = None
    values: list[TaxonomyValueOut] = Field(default_factory=list)


class EndorsementOrgOut(BaseModel):
    id: str
    slug: str
    name: str


class EndorsementOut(BaseModel):
    id: str
    # Display name of the endorser (denormalised org name; free text on
    # historical stamps from before the org requirement).
    body: str
    organisation: EndorsementOrgOut | None = None
    note: str | None = None
    created_at: datetime
    withdrawn_at: datetime | None = None
    withdrawal_note: str | None = None


class VersionOut(BaseModel):
    id: str
    concept_id: str
    branch_id: str | None = None
    language: str
    canonical_form: str
    definition_md: str
    status: str
    tags: list[str] = Field(default_factory=list)
    note: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    created_by: UserOut | None = None
    annotations: list[AnnotationOut] = Field(default_factory=list)
    endorsements: list[EndorsementOut] = Field(default_factory=list)


class EdgeOut(BaseModel):
    child_id: str
    parent_id: str
    edge_type: str
    ordinal: int = 0
    note: str | None = None


class BranchOut(BaseModel):
    id: str
    name: str
    head_version_id: str | None = None


class ConceptGraphOut(BaseModel):
    concept_id: str
    collection: CollectionOut
    versions: list[VersionOut]
    edges: list[EdgeOut]
    branches: list[BranchOut]


class RelationOut(BaseModel):
    id: str
    relation_type: str
    direction: Literal["out", "in"]
    other_concept_id: str
    other_canonical_form: str
    other_collection_slug: str
    note: str | None = None


class TranslationOut(BaseModel):
    concept_id: str
    version_id: str
    language: str
    canonical_form: str


class ConceptOut(BaseModel):
    id: str
    collection: CollectionOut
    created_at: datetime
    head: VersionOut | None = None
    branches: list[BranchOut] = Field(default_factory=list)
    relations: list[RelationOut] = Field(default_factory=list)
    translations: list[TranslationOut] = Field(default_factory=list)
    version_count: int = 0
    # Iteration 4: is the calling user watching this concept?
    watching: bool = False
    # Begreppssidans omgörning (2026-07): counters for the concept page's
    # engagement strip. Always present (0 when there is nothing to count).
    watcher_count: int = 0
    # The CALLER's own pin_lists containing this concept — 0 for anonymous.
    list_count: int = 0
    comment_count: int = 0
    proposal_count: int = 0
    open_proposal_count: int = 0
    activity_count: int = 0
    # Taxonomies (2026-07-11): global categories + the collection's own
    # (e.g. parts). Assigned on the concept; see ConceptTaxonomyOut.
    taxonomies: list[ConceptTaxonomyOut] = Field(default_factory=list)


class ConceptListItem(BaseModel):
    id: str
    canonical_form: str
    language: str
    definition_snippet: str
    # Länkbevarande variant för begreppskorten (kontraktets princip 7):
    # markdown-länkar/korsreferenser överlever trunkeringen och renderas
    # klickbara i kortutdraget. definition_snippet är kvar för klartextytor.
    definition_snippet_md: str = ""
    tags: list[str] = Field(default_factory=list)
    # Global category names (the cross-collection search axis) — assigned on
    # the concept, shown as distinct chips next to the version-borne tags.
    categories: list[str] = Field(default_factory=list)
    status: str
    collection_slug: str
    collection_name: str
    collection_year: int | None = None
    # Samlingsbadgens scopefärger (kontraktstillägg 2026-07-15, v1:s typfärger)
    collection_visibility: str = "public"
    collection_has_org: bool = False
    version_count: int = 1
    updated_at: datetime


class ConceptListOut(BaseModel):
    items: list[ConceptListItem]
    total: int


class ConceptCreate(BaseModel):
    collection_id: str
    canonical_form: CanonicalForm
    language: str = "sv"
    definition_md: DefinitionMd = ""
    # 'endorsed' is accepted for legacy clients but coerced to 'proposed'
    # in graph.coerce_status; everything else is a 422 (Bengt #8).
    status: Literal["draft", "proposed", "deprecated", "superseded", "endorsed"] = "draft"
    tags: Tags = Field(default_factory=list)
    note: Note | None = None
    translated_from_version_id: str | None = None
    spawned_from_id: str | None = None


class VersionCreate(BaseModel):
    mode: Literal["revise", "branch", "synthesize", "translate"]
    base_version_id: str
    canonical_form: CanonicalForm
    definition_md: DefinitionMd
    language: str | None = None
    status: Literal["draft", "proposed", "deprecated", "superseded", "endorsed"] = "draft"
    tags: Tags | None = None
    note: Note | None = None
    branch_name: BranchName | None = None
    extra_parent_ids: list[str] = Field(default_factory=list)
    source_version_id: str | None = None


class PromoteIn(BaseModel):
    version_id: str
    note: Note | None = None
    branch_name: BranchName = "main"
    # Content overrides — the "edit a historical version" flow. When absent
    # the promoted head copies the old version verbatim (plain restore).
    canonical_form: CanonicalForm | None = None
    definition_md: DefinitionMd | None = None
    tags: Tags | None = None
    status: Literal["draft", "proposed", "deprecated", "superseded", "endorsed"] | None = None


class RelationCreate(BaseModel):
    relation_type: str
    from_concept_id: str
    to_concept_id: str
    note: Note | None = None


class ListCreate(BaseModel):
    name: str
    purpose: str | None = None


class ListItemCreate(BaseModel):
    concept_id: str
    version_id: str | None = None
    follow_head: bool = False
    note: Note | None = None


class ListItemOut(BaseModel):
    id: str
    concept_id: str
    version_id: str | None = None
    follow_head: bool
    ordinal: int
    note: str | None = None
    canonical_form: str | None = None


class ListOut(BaseModel):
    id: str
    name: str
    purpose: str | None = None
    created_at: datetime
    items: list[ListItemOut] = Field(default_factory=list)


class StatsOut(BaseModel):
    collections: int
    concepts: int
    versions: int
    relations: int
    users: int


class AiDraftIn(BaseModel):
    intent: Literal["translate", "synthesize"]
    version_ids: list[str] = Field(default_factory=list)
    target_language: Literal["sv", "en"] | None = None
    guidance: str | None = None
    model: str | None = None
    # Iteration 4: a SavedPrompt whose text is prepended to the guidance; echoed
    # back so the frontend can stamp it into the version's provenance.
    prompt_id: str | None = None


class AiDraftOut(BaseModel):
    canonical_form: str
    definition_md: str
    note_suggestion: str
    model: str
    provider: str
    prompt_id: str | None = None


# ── Iteration 4: change proposals, discussions, activity, prompts, permalinks ──


class ProposalOut(BaseModel):
    id: str
    concept_id: str
    canonical_form: str
    collection_slug: str
    source_branch_name: str
    target_branch: str = "main"
    title: str
    description: str | None = None
    status: str
    created_by: UserOut | None = None
    created_at: datetime
    resolved_by: UserOut | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    source_head: VersionOut | None = None
    target_head: VersionOut | None = None
    base_version_id: str | None = None


class CommentOut(BaseModel):
    id: str
    concept_id: str
    proposal_id: str | None = None
    body: str
    created_by: UserOut | None = None
    created_at: datetime


class ActivityItemOut(BaseModel):
    kind: Literal[
        "version",
        "branch",
        "merge",
        "endorsement",
        "comment",
        "proposal",
        "proposal_merged",
        "proposal_rejected",
        "proposal_withdrawn",
    ]
    at: datetime
    actor: UserOut | None = None
    concept_id: str
    canonical_form: str
    summary: str
    # Historikvyns händelselager (2026-07): the version this row concerns —
    # a version/branch/merge row's own id, an endorsement's endorsed version,
    # a proposal row's source-branch head. Null for comments (no single
    # version is "the" subject).
    version_id: str | None = None


class SavedPromptOut(BaseModel):
    id: str
    name: str
    intent: str
    text: str
    shared: bool = False
    owner_handle: str | None = None


class VersionCollectionRefOut(BaseModel):
    slug: str
    name: str
    year: int | None = None
    visibility: str = "public"
    has_org: bool = False


class MostWatchedOut(BaseModel):
    """One row of GET /concepts/most-watched — the home page's watch-list."""

    id: str
    canonical_form: str
    language: str
    watcher_count: int
    collection: VersionCollectionRefOut


class UnseenCountOut(BaseModel):
    """GET /activity/unseen-count — the header bell's badge count."""

    count: int


class VersionPermalinkOut(VersionOut):
    """The citable frozen version (VISION §10): VersionOut + its collection
    and whether any branch still points at it."""

    collection: VersionCollectionRefOut
    is_head: bool = False
