"""Endorsements — the write path (VISION §4.3, reworked 2026-07-11).

An endorsement is an ORGANISATION's attributed, withdrawable flag on one
specific version: "this is the definition we use." It is a relation
org → version, never a property of the text — several organisations may
flag different versions of the same concept (coexistence-first canon).

Rights:
- Stamping: admins of an APPROVED, non-suspended organisation, on behalf of
  their OWN organisation only — regardless of who owns the collection (that
  is the whole point: any org can flag its own definition of a shared
  concept). Super admins do NOT stamp (an endorsement without an
  organisation behind it is meaningless) — they only withdraw.
- Withdrawal: admins of the endorsing organisation, or super admins.
  Historical stamps without an organisation: super admins only.

One ACTIVE flag per organisation and concept: a new stamp auto-withdraws
the organisation's previous stamp on any other version of the same concept
(the record is never deleted — withdrawal is an attributed event).

The note (the "why") is REQUIRED on both stamping and withdrawal — an
endorsement without a rationale is worthless provenance.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import (
    admin_org_ids,
    can_view_collection,
    current_user,
    ensure_actor_can_write,
    is_org_admin,
)
from ..errors import api_error
from ..models import Collection, Endorsement, Organisation, User, Version, utcnow

router = APIRouter(tags=["endorsements"])


class EndorseIn(BaseModel):
    note: str = Field(min_length=1)
    # Acting organisation (multi-org, 2026-07): required when the actor is
    # admin of several orgs; auto-resolved when there is exactly one.
    organisation_id: str | None = None


class WithdrawIn(BaseModel):
    note: str = Field(min_length=1)


def _require_endorsing_org(
    db: Session, user: User | None, organisation_id: str | None
) -> Organisation:
    """Resolve the ACTING organisation: the actor must be an admin of an
    approved, non-suspended organisation — the stamp is made on that
    organisation's behalf. With several admin memberships the acting org must
    be named explicitly; with exactly one it is auto-resolved. Super admins do
    not stamp: an endorsement is an organisation's statement, not a platform
    act."""
    if user is None:
        raise api_error(401, "login_required", "Login required.")
    ensure_actor_can_write(user)
    candidate_ids = admin_org_ids(user)
    if not candidate_ids:
        raise api_error(
            403,
            "endorsement_requires_org_admin",
            "Endorsing is done on behalf of an organisation; you must be an "
            "organisation administrator to endorse.",
        )
    candidates = [
        org
        for org in (
            db.query(Organisation).filter(Organisation.id.in_(candidate_ids)).all()
        )
        if org.is_approved and not org.is_suspended
    ]
    if organisation_id is not None:
        chosen = next((org for org in candidates if org.id == organisation_id), None)
        if chosen is None:
            raise api_error(
                403,
                "endorsement_org_not_eligible",
                "You can only endorse for an approved organisation where "
                "you are an administrator.",
                organisation_id=organisation_id,
            )
        return chosen
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise api_error(
            403,
            "org_not_approved",
            "The organisation is not approved yet; endorsing requires an "
            "approved organisation.",
        )
    raise api_error(
        422,
        "endorsement_org_ambiguous",
        "You administer several organisations; specify which organisation "
        "you are endorsing for.",
    )


def _endorsement_out(endorsement: Endorsement) -> schemas.EndorsementOut:
    org = endorsement.organisation
    return schemas.EndorsementOut(
        id=endorsement.id,
        body=endorsement.body,
        organisation=(
            schemas.EndorsementOrgOut(id=org.id, slug=org.slug, name=org.name) if org else None
        ),
        note=endorsement.note,
        created_at=endorsement.created_at,
        withdrawn_at=endorsement.withdrawn_at,
        withdrawal_note=endorsement.withdrawal_note,
    )


def _ensure_not_archived(collection: Collection) -> None:
    # Archived blocks ALL writes — endorsements included. Locked does not:
    # a stamp is a statement ABOUT a version, not a change of its content.
    if collection.is_archived:
        raise api_error(
            423,
            "collection_archived",
            "The collection is archived; unarchive it to make changes.",
        )


@router.post(
    "/versions/{version_id}/endorsements",
    response_model=schemas.EndorsementOut,
    status_code=201,
)
def endorse_version(
    version_id: str,
    payload: EndorseIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.EndorsementOut:
    version = db.get(Version, version_id)
    if version is None or not can_view_collection(user, version.concept.collection):
        raise api_error(404, "version_not_found", "Version not found", version_id=version_id)
    org = _require_endorsing_org(db, user, payload.organisation_id)
    _ensure_not_archived(version.concept.collection)

    # One active flag per organisation and concept. The join on Version covers
    # pre-013 rows whose denormalised concept_id is still NULL.
    active = (
        db.query(Endorsement)
        .join(Version, Endorsement.version_id == Version.id)
        .filter(
            Version.concept_id == version.concept_id,
            Endorsement.organisation_id == org.id,
            Endorsement.withdrawn_at.is_(None),
        )
        .all()
    )
    for previous in active:
        if previous.version_id == version.id:
            raise api_error(
                409,
                "endorsement_exists",
                "The organisation has already endorsed this version.",
            )
    for previous in active:
        # The flag MOVES: the old stamp is auto-withdrawn, never deleted.
        previous.withdrawn_at = utcnow()
        previous.withdrawal_note = "Ersatt av nytt intyg för en annan version av begreppet."

    endorsement = Endorsement(
        version_id=version.id,
        organisation_id=org.id,
        concept_id=version.concept_id,
        body=org.name,
        note=payload.note.strip(),
        stamped_by=user.id if user else None,
    )
    db.add(endorsement)
    db.commit()
    return _endorsement_out(endorsement)


@router.post("/endorsements/{endorsement_id}/withdraw", response_model=schemas.EndorsementOut)
def withdraw_endorsement(
    endorsement_id: str,
    payload: WithdrawIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.EndorsementOut:
    endorsement = db.get(Endorsement, endorsement_id)
    if endorsement is None or not can_view_collection(
        user, endorsement.version.concept.collection
    ):
        raise api_error(
            404, "endorsement_not_found", "Endorsement not found", endorsement_id=endorsement_id
        )
    if user is None:
        raise api_error(401, "login_required", "Login required.")
    ensure_actor_can_write(user)
    # Withdrawal: the endorsing org's admins, or super admins. Historical
    # stamps without an organisation: super admins only.
    if not user.is_super_admin and not (
        endorsement.organisation_id is not None
        and is_org_admin(user, endorsement.organisation_id)
    ):
        raise api_error(
            403,
            "endorsement_withdraw_forbidden",
            "Only administrators of the endorsing organisation or super "
            "administrators can withdraw the endorsement.",
        )
    _ensure_not_archived(endorsement.version.concept.collection)
    if endorsement.withdrawn_at is not None:
        raise api_error(
            409, "endorsement_already_withdrawn", "The endorsement is already withdrawn."
        )
    endorsement.withdrawn_at = utcnow()
    endorsement.withdrawal_note = payload.note.strip()
    db.commit()
    return _endorsement_out(endorsement)
