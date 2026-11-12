"""Pinned lists — the procurement profile pattern (VISION §3).

The list export endpoint (`GET /lists/{id}/export`) lives in exports.py
together with the collection exports, sharing the format serializers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import graph, schemas
from ..db import get_db
from ..deps import can_view_collection, current_user, ensure_actor_can_write, require_user
from ..errors import api_error
from ..models import Concept, ListItem, PinList, User, Version

router = APIRouter(prefix="/lists", tags=["lists"])


def _owned_list_or_404(db: Session, list_id: str, user: User) -> PinList:
    """Fetch a list the caller owns, else 404 (existence is not disclosed).
    Pinned lists are private procurement profiles (VISION §3) — only the owner
    (or a super admin) may read or mutate them (säkerhetsfix 2026-07-15)."""
    pin_list = db.get(PinList, list_id)
    if pin_list is None or (pin_list.owner_id != user.id and not user.is_super_admin):
        raise api_error(404, "list_not_found", "List not found")
    return pin_list


def _list_out(db: Session, pin_list: PinList) -> schemas.ListOut:
    items = []
    for item in sorted(pin_list.items, key=lambda i: i.ordinal):
        version = _resolve_version(db, item)
        items.append(
            schemas.ListItemOut(
                id=item.id,
                concept_id=item.concept_id,
                version_id=item.version_id,
                follow_head=item.follow_head,
                ordinal=item.ordinal,
                note=item.note,
                canonical_form=version.canonical_form if version else None,
            )
        )
    return schemas.ListOut(
        id=pin_list.id,
        name=pin_list.name,
        purpose=pin_list.purpose,
        created_at=pin_list.created_at,
        items=items,
    )


def _resolve_version(db: Session, item: ListItem) -> Version | None:
    if item.follow_head:
        concept = db.get(Concept, item.concept_id)
        return graph.head_of(db, concept) if concept else None
    return db.get(Version, item.version_id) if item.version_id else None


@router.get("", response_model=list[schemas.ListOut])
def list_lists(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.ListOut]:
    # Own lists only (säkerhetsfix 2026-07-15 — was returning every user's
    # lists). Anonymous callers own none, so an empty list keeps the page calm.
    if user is None:
        return []
    return [
        _list_out(db, pl) for pl in db.query(PinList).filter(PinList.owner_id == user.id).all()
    ]


@router.post("", response_model=schemas.ListOut, status_code=201)
def create_list(
    payload: schemas.ListCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.ListOut:
    # Same actor gate as concept writes: pending-review accounts read only
    # (the gap found in the claim-security pass, 2026-08-12).
    ensure_actor_can_write(user)
    pin_list = PinList(name=payload.name, purpose=payload.purpose, owner_id=user.id)
    db.add(pin_list)
    db.commit()
    return _list_out(db, pin_list)


@router.get("/{list_id}", response_model=schemas.ListOut)
def get_list(
    list_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.ListOut:
    return _list_out(db, _owned_list_or_404(db, list_id, user))


@router.post("/{list_id}/items", response_model=schemas.ListOut, status_code=201)
def add_item(
    list_id: str,
    payload: schemas.ListItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.ListOut:
    ensure_actor_can_write(user)
    pin_list = _owned_list_or_404(db, list_id, user)
    concept = db.get(Concept, payload.concept_id)
    # Can't pin what you can't see — mirrors the read guard (404, not 403).
    if concept is None or not can_view_collection(user, concept.collection):
        raise api_error(404, "concept_not_found", "Concept not found")
    version_id = payload.version_id
    if version_id is not None:
        pinned = db.get(Version, version_id)
        # A pin must point into the item's own concept — otherwise a list could
        # quote (and export) content from a concept the pin never named.
        if pinned is None or pinned.concept_id != concept.id:
            raise api_error(400, "version_mismatch", "version_id does not belong to concept_id.")
    if not payload.follow_head and version_id is None:
        head = graph.head_of(db, concept)
        version_id = head.id if head else None  # pin to current head explicitly
    item = ListItem(
        list_id=list_id,
        concept_id=payload.concept_id,
        version_id=version_id,
        follow_head=payload.follow_head,
        ordinal=len(pin_list.items),
        note=payload.note,
    )
    db.add(item)
    db.commit()
    db.refresh(pin_list)
    return _list_out(db, pin_list)


@router.delete("/{list_id}/items/{item_id}", status_code=204)
def delete_item(
    list_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """Remove an item from a list and close the ordinal gap it leaves."""
    pin_list = _owned_list_or_404(db, list_id, user)
    item = db.get(ListItem, item_id)
    if item is None or item.list_id != list_id:
        raise api_error(404, "list_item_not_found", "List item not found")
    db.delete(item)
    remaining = sorted((i for i in pin_list.items if i.id != item_id), key=lambda i: i.ordinal)
    for ordinal, sibling in enumerate(remaining):
        sibling.ordinal = ordinal
    db.commit()
