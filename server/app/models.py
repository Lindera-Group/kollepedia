"""Kollepedia NG domain model.

The heart of the system (VISION §4): concepts are durable identities whose
history is a DAG of immutable versions. The bespoke surface is deliberately
narrow: append-only version creation, explicit branching, explicit synthesis,
head promotion. Edges are only ever created together with a brand-new child
version, which makes the graph acyclic by construction.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


VERSION_STATUSES = ("draft", "proposed", "endorsed", "deprecated", "superseded")
EDGE_TYPES = (
    "revised_from",
    "branched_from",
    "synthesized_from",
    "translated_from",
    "promoted_from",
)
RELATION_TYPES = (
    "related_to",
    "broader",
    "narrower",
    "exact_match",
    "close_match",
    "supersedes",
)
ORG_ROLES = ("admin", "editor", "viewer")
# Membership kind is display/relationship semantics, orthogonal to role:
# member = belongs to the organisation; guest = external participant
# (consultant, researcher). Guests can never hold the admin role or own an org.
MEMBERSHIP_KINDS = ("member", "guest")
# commercial → paid account (badge-only placeholder for now); academy and
# industry_association → member-financed non-commercial, super-admin-confirmed
# at approval time (= fee-exempt).
ORG_TYPES = ("commercial", "academy", "industry_association")
# private: the creator's personal sandbox — visible to the creator (and super
# admins) only. Publishing/collaborating requires assigning an organisation.
COLLECTION_VISIBILITIES = ("public", "org_private", "private")
# Iteration 4: per-collection editing policy (public ≠ freely editable).
# org: owning-org members only; anyone: any logged-in identity; open: wiki
# mode — even anonymous visitors (created_by NULL, provenance anonymous:true).
COLLECTION_EDIT_POLICIES = ("org", "anyone", "open")
PROPOSAL_STATUSES = ("open", "merged", "rejected", "withdrawn")
EMAIL_STATUSES = ("queued", "sent", "blocked", "outbox")
PROMPT_INTENTS = ("synthesize", "translate", "extract")


class Base(DeclarativeBase):
    pass


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Super admins approve new organisations (old-gen parity).
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Suspended organisations: writes in the org's context are blocked.
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # commercial | academy | industry_association — claimed at creation,
    # confirmed by a super admin at approval. NULL until claimed/confirmed.
    org_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # THE economic-responsibility anchor. Soft reference to users.id (a hard FK
    # would make users ↔ organisations circular for SQLite's create_all). The
    # UNIQUE index structurally enforces both "one owner per org" and "one
    # owned org per user" (SQLite unique indexes allow multiple NULLs). The
    # owner must always hold an active admin membership — app-enforced.
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Soft reference to users.id — see owner_user_id.
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ux_organisations_owner", "owner_user_id", unique=True),
        CheckConstraint(
            f"org_type IS NULL OR org_type IN {ORG_TYPES!r}", name="organisations_type_check"
        ),
    )


class OrgMembership(Base):
    """A user's membership in ONE organisation — many rows per user (2026-07).

    role governs permissions (admin/editor/viewer); kind is the relationship
    (member/guest — guests can never be admin). Ended memberships are
    end-dated (`ended_at`), never deleted: "aldrig radera, bara dölja".
    is_public is the per-membership opt-out for the public author page."""

    __tablename__ = "org_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    organisation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organisations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member", server_default="member"
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    # Soft reference to users.id (the inviting admin), provenance only.
    invited_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organisation: Mapped["Organisation"] = relationship("Organisation")

    __table_args__ = (
        CheckConstraint(f"role IN {ORG_ROLES!r}", name="org_memberships_role_check"),
        CheckConstraint(f"kind IN {MEMBERSHIP_KINDS!r}", name="org_memberships_kind_check"),
        # One ACTIVE membership per user and organisation; ended rows may pile
        # up as history (re-invitations create a fresh row).
        Index(
            "ux_membership_active",
            "user_id",
            "organisation_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
        ),
    )


class AdminEvent(Base):
    """Audit log for super-admin actions (guardrail G5): approve/suspend orgs,
    suspend/restore users, ownership transfers, … Append-only."""

    __tablename__ = "admin_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class User(Base):
    """A person. Memberships live in org_memberships (many orgs per user,
    2026-07); ownership of at most ONE org via organisations.owner_user_id.
    password_hash NULL = claimable imported author."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    handle: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    affiliation: Mapped[str | None] = mapped_column(String(500))
    web_url: Mapped[str | None] = mapped_column(Text)
    # Iteration 4 (email-first identity): the login identifier. Verified via a
    # one-time emailed token; changing the address re-verifies.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Inactive accounts are blocked from login/refresh and all writes (iteration 3).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Manual admin outreach to imported authors (migration 003). NULL = not
    # contacted; values used: 'contacted' | 'opted_out'. Check-free on purpose —
    # opt-out sanctity is enforced in the outreach router, never overwritten.
    outreach_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Individual profile (migration 008): a short bio; together with the
    # pre-existing web_url it makes up the public author-page presentation.
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Header-bell read receipt (migration 009): NULL means "never checked" —
    # every event in the user's watched concepts counts as unseen. Set to now()
    # by POST /activity/seen.
    activity_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # SPAM defence (migration 008): suspicious registrations land in 'pending'
    # and cannot write until a super admin approves. 'rejected' blocks writes
    # permanently (the account can still log in and read).
    review_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="approved", server_default="approved"
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    # ALL membership rows (incl. ended ones) — filter on ended_at IS NULL for
    # the active set; deps.py's helpers do exactly that.
    memberships: Mapped[list["OrgMembership"]] = relationship(
        "OrgMembership", back_populates="user"
    )


class RefreshToken(Base):
    """Opaque, rotating refresh token (iteration 3). Only the SHA-256 hash is
    stored; the raw value lives in an httpOnly cookie scoped to /api/v1/auth.
    Rotation: every /auth/refresh revokes the presented token and issues a
    fresh one — a revoked token being replayed is a hard 401."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ResetToken(Base):
    """One-time password-reset token (iteration 3, no email infra): a super admin
    mints a link, hands it over manually, and /auth/reset consumes it."""

    __tablename__ = "reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ActivationToken(Base):
    """One-time author-activation token (2026-08-13; new table, so startup
    create_all covers the schema — no ALTER migration needed): a super admin
    mints a personal /activate link from the outreach workbench;
    register-with-claim consumes it. A claim WITH a valid token is verified
    by construction; a claim WITHOUT one falls back to manual review."""

    __tablename__ = "activation_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class UsedNonce(Base):
    """Single-use registry for solved proof-of-work challenges (migration 008).
    A challenge salt may buy exactly one registration attempt — replaying a
    solved challenge hits the primary key and is refused. Expired rows are
    pruned opportunistically on insert."""

    __tablename__ = "used_nonces"

    nonce: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RegistrationEvent(Base):
    """One row per registration attempt (migration 008), used for the
    same-source velocity heuristic. The source is a SHA-256 of the client IP —
    equality is all the heuristic needs, so the address itself is never
    stored. Rows older than the velocity window are pruned on insert."""

    __tablename__ = "registration_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Collection(Base):
    """A curated vocabulary where concepts live and evolve (VISION §3)."""

    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Machine-readable content-rights statement (VISION §7): label, url, odrl…
    licence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    organisation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organisations.id"), nullable=True
    )
    # public: readable by everyone; org_private: members of the owning org only.
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    # Iteration 4: who may write concepts/versions here (independent of visibility).
    edit_policy: Mapped[str] = mapped_column(String(20), default="anyone", nullable=False)
    # Iteration 3 (VISION §4.3): locked → writes only for owning-org admins/super;
    # archived → all writes blocked and hidden from listings by default.
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Rich collection metadata restored from the old site (migration 007).
    # The three provenance strings are PATCH-editable with manage rights.
    source_url: Mapped[str | None] = mapped_column(Text)
    archive_url: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[str | None] = mapped_column(Text)
    # Imported provenance, read-only through the API for now:
    # sources — old sources_json array [{label_sv, label_en, url, filename, type}, …];
    # locales — {sv: {name, short_description, description}, en: {…}} — the rich
    # bilingual layer. Collection.description stays the short fallback.
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    locales: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    concepts: Mapped[list["Concept"]] = relationship("Concept", back_populates="collection")
    organisation: Mapped[Optional["Organisation"]] = relationship("Organisation")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint(
            f"visibility IN {COLLECTION_VISIBILITIES!r}", name="collections_visibility_check"
        ),
        CheckConstraint(
            f"edit_policy IN {COLLECTION_EDIT_POLICIES!r}", name="collections_edit_policy_check"
        ),
    )


class Concept(Base):
    """The durable identity of an idea. Never edited directly — only versioned."""

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collections.id"), nullable=False, index=True
    )
    # Cross-concept lineage: "ett begrepp föder ett annat" (VISION §4.1).
    spawned_from_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    collection: Mapped["Collection"] = relationship("Collection", back_populates="concepts")
    versions: Mapped[list["Version"]] = relationship(
        "Version", back_populates="concept", cascade="all, delete-orphan"
    )
    branches: Mapped[list["Branch"]] = relationship(
        "Branch", back_populates="concept", cascade="all, delete-orphan"
    )


class Branch(Base):
    """A named head pointer. Every concept has a 'main' branch."""

    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    head_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    concept: Mapped["Concept"] = relationship("Concept", back_populates="branches")

    __table_args__ = (UniqueConstraint("concept_id", "name", name="uq_branch_concept_name"),)


class Version(Base):
    """An immutable snapshot of a concept. There is no update path for content."""

    __tablename__ = "versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True, index=True
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="sv")
    canonical_form: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    definition_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    # Tags are versioned so categorisation history animates in the Time Machine.
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # The "why" — commit message of the change (VISION §4.3).
    note: Mapped[str | None] = mapped_column(Text)
    # {kind: human|llm|import, model?, prompt_id?, provider?, source?, …} → PROV-O.
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    concept: Mapped["Concept"] = relationship("Concept", back_populates="versions")
    creator: Mapped[Optional["User"]] = relationship("User")
    annotations: Mapped[list["Annotation"]] = relationship(
        "Annotation", back_populates="version", cascade="all, delete-orphan"
    )
    endorsements: Mapped[list["Endorsement"]] = relationship(
        "Endorsement", back_populates="version", cascade="all, delete-orphan"
    )
    parent_edges: Mapped[list["VersionEdge"]] = relationship(
        "VersionEdge",
        foreign_keys="VersionEdge.child_id",
        back_populates="child",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(f"status IN {VERSION_STATUSES!r}", name="versions_status_check"),
    )


class VersionEdge(Base):
    """Typed lineage edge: child version → parent version. Carries its own note."""

    __tablename__ = "version_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=False, index=True
    )
    parent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Ordinal 0 is the primary parent (matters for synthesized_from).
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    child: Mapped["Version"] = relationship(
        "Version", foreign_keys=[child_id], back_populates="parent_edges"
    )
    parent: Mapped["Version"] = relationship("Version", foreign_keys=[parent_id])

    __table_args__ = (
        CheckConstraint(f"edge_type IN {EDGE_TYPES!r}", name="version_edges_type_check"),
        UniqueConstraint("child_id", "parent_id", "edge_type", name="uq_edge"),
    )


class Annotation(Base):
    """Stand-off annotation over a version's definition text (W3C-shaped, VISION §4.2)."""

    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=False, index=True
    )
    attr_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote: Mapped[str | None] = mapped_column(Text)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    version: Mapped["Version"] = relationship("Version", back_populates="annotations")


class ConceptRelation(Base):
    """Typed, note-bearing relation between concepts (VISION §4.4)."""

    __tablename__ = "concept_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    to_concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            f"relation_type IN {RELATION_TYPES!r}", name="concept_relations_type_check"
        ),
    )


class Endorsement(Base):
    """An organisation's attributed, withdrawable flag on ONE version: "this
    is the definition we use" (VISION §4.3, reworked 2026-07-11). A relation
    org → version — never a property of the text; several organisations may
    flag different versions of the same concept (coexistence-first canon).
    One ACTIVE flag per organisation and concept — a new stamp auto-withdraws
    the organisation's previous one (the record is never deleted)."""

    __tablename__ = "endorsements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=False, index=True
    )
    # NULL only on historical/imported stamps from before the org requirement
    # (migration 010); every new stamp carries the endorsing organisation.
    organisation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organisations.id"), nullable=True, index=True
    )
    # Denormalised from the version (migration 013) so the one-active-flag-
    # per-org-and-concept invariant is DB-enforced, not just app-enforced.
    concept_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=True, index=True
    )
    # Display name of the endorser — denormalised org name on new stamps,
    # free text on historical rows.
    body: Mapped[str] = mapped_column(String(200), nullable=False)
    stamped_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrawal_note: Mapped[str | None] = mapped_column(Text)

    version: Mapped["Version"] = relationship("Version", back_populates="endorsements")
    organisation: Mapped["Organisation"] = relationship("Organisation")

    __table_args__ = (
        # Bengt #6: two near-simultaneous stamps by the same org on the same
        # concept cannot both land active — the partial unique index is the
        # backstop behind the app-level auto-withdraw.
        Index(
            "uq_endorsement_active_org_concept",
            "organisation_id",
            "concept_id",
            unique=True,
            sqlite_where=text("withdrawn_at IS NULL AND organisation_id IS NOT NULL"),
        ),
    )


class LegacyId(Base):
    """Prototype term_id → NG concept alias. Imported definitions contain
    [Label](#<old-term-id>) links; versions are immutable, so instead of
    rewriting them the concept lookup resolves legacy ids transparently."""

    __tablename__ = "legacy_ids"

    legacy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )


class PinList(Base):
    """A purpose-built selection of pinned term-versions (VISION §3: List)."""

    __tablename__ = "pin_lists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    items: Mapped[list["ListItem"]] = relationship(
        "ListItem", back_populates="pin_list", cascade="all, delete-orphan"
    )


class EmailMessage(Base):
    """Every outbound email the system ever produced (iteration 4). SAFETY: the
    allowlist in app/email.py stores non-allowlisted recipients as 'blocked'
    without ever sending; the default backend stores everything as 'outbox'."""

    __tablename__ = "email_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    to_addr: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="outbox")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN {EMAIL_STATUSES!r}", name="email_messages_status_check"),
    )


class EmailVerifyToken(Base):
    """One-time email-verification token (48 h). Stores the address it was
    minted for, so changing the email invalidates in-flight verifications."""

    __tablename__ = "email_verify_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ChangeProposal(Base):
    """A 'PR för begrepp' (VISION §10, iteration 4): asks the collection's stewards
    to merge a named branch into main. Merging goes through app.graph like
    every other version write — fast-forward or explicit synthesis."""

    __tablename__ = "change_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    source_branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=False, index=True
    )
    target_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)

    concept: Mapped["Concept"] = relationship("Concept")
    source_branch: Mapped["Branch"] = relationship("Branch")

    __table_args__ = (
        CheckConstraint(f"status IN {PROPOSAL_STATUSES!r}", name="change_proposals_status_check"),
    )


class Comment(Base):
    """Flat discussion post on a concept or a change proposal (iteration 4)."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), nullable=False, index=True
    )
    proposal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("change_proposals.id"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Watch(Base):
    """User ⇄ concept subscription feeding the personal activity feed."""

    __tablename__ = "watches"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SavedPrompt(Base):
    """Reusable AI guidance preset (VISION §4.3: prompts are first-class).
    prompt_id is stamped into version provenance when a draft used it."""

    __tablename__ = "saved_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    intent: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint(f"intent IN {PROMPT_INTENTS!r}", name="saved_prompts_intent_check"),
    )


class ListItem(Base):
    __tablename__ = "list_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    list_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pin_lists.id"), nullable=False, index=True
    )
    concept_id: Mapped[str] = mapped_column(String(36), ForeignKey("concepts.id"), nullable=False)
    # Pin to a specific version; follow_head=True means "pin to whatever main's head is".
    version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("versions.id"), nullable=True
    )
    follow_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    pin_list: Mapped["PinList"] = relationship("PinList", back_populates="items")


class Taxonomy(Base):
    """A curated controlled vocabulary (2026-07-11, plan NG_TAXONOMIES...).

    Two scopes, one machinery:
    - 'global'     — the cross-collection categories (search axis). Curated by
      super admins and DELIBERATELY mutable over time to keep global search
      simple — the vocabulary follows the corpus, not the other way around.
    - 'collection' — a collection's own structure, e.g. the source standard's
      Parts (EN 12896) with min=max=1, or subject areas. Curated by the
      collection's managers.

    min_per_concept is SOFT (validated in UI/import as a warning);
    max_per_concept is HARD when set (parts use max=1)."""

    __tablename__ = "taxonomies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="collection")
    collection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("collections.id"), nullable=True, index=True
    )
    min_per_concept: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_per_concept: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    values: Mapped[list["TaxonomyValue"]] = relationship(
        "TaxonomyValue",
        back_populates="taxonomy",
        order_by="TaxonomyValue.position",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("slug", "collection_id", name="uq_taxonomy_slug_scope"),)


class TaxonomyValue(Base):
    __tablename__ = "taxonomy_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    taxonomy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("taxonomies.id"), nullable=False, index=True
    )
    # The taxonomy level is BILINGUAL (unlike free tags): name = Swedish,
    # name_en = English (falls back to name when NULL).
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    taxonomy: Mapped["Taxonomy"] = relationship("Taxonomy", back_populates="values")

    __table_args__ = (UniqueConstraint("taxonomy_id", "name", name="uq_taxonomy_value_name"),)


class ConceptTaxonomyValue(Base):
    """Assignment on the CONCEPT (not the version): recategorisation is
    curation work and must not mint new text versions — the audit trail is
    added_by/added_at, mirroring the endorsement-rework reasoning."""

    __tablename__ = "concept_taxonomy_values"

    concept_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("concepts.id"), primary_key=True
    )
    value_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("taxonomy_values.id"), primary_key=True
    )
    added_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    value: Mapped["TaxonomyValue"] = relationship("TaxonomyValue")
