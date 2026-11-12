"""Citable version permalinks (VISION §10 "pillar", iteration 4).

GET /versions/{id} is the stable, public address of one immutable version —
the thing a report or standard can cite. Visibility follows the concept's
collection (org_private → 404 for outsiders); `is_head` says whether any
branch still points at this exact version.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..deps import can_view_collection, current_user
from ..errors import api_error
from ..models import Branch, User, Version
from ..serialize import version_out

router = APIRouter(tags=["versions"])


@router.get("/versions/{version_id}", response_model=schemas.VersionPermalinkOut)
def get_version(
    version_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> schemas.VersionPermalinkOut:
    version = db.get(Version, version_id)
    if version is None or not can_view_collection(user, version.concept.collection):
        raise api_error(404, "version_not_found", "Version not found")
    collection = version.concept.collection
    is_head = (
        db.query(Branch).filter(Branch.head_version_id == version.id).first() is not None
    )
    return schemas.VersionPermalinkOut(
        **version_out(version).model_dump(),
        collection=schemas.VersionCollectionRefOut(
                slug=collection.slug,
                name=collection.name,
                year=collection.year,
                visibility=collection.visibility,
                has_org=collection.organisation_id is not None,
            ),
        is_head=is_head,
    )
