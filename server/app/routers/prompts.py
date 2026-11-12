"""Saved AI prompts (VISION §4.3: prompts are first-class, iteration 4).

A SavedPrompt is a reusable guidance preset for the AI dialogs. Listing shows
the caller's own prompts plus everything shared; /ai/draft accepts a
prompt_id, prepends the prompt text to the guidance and echoes the id back so
the frontend can stamp it into the resulting version's provenance.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import schemas
from ..db import get_db
from ..deps import current_user, require_user
from ..errors import api_error
from ..features import require_feature
from ..models import PROMPT_INTENTS, SavedPrompt, User

router = APIRouter(
    prefix="/prompts", tags=["prompts"], dependencies=[Depends(require_feature("ai"))]
)


class PromptCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intent: Literal["synthesize", "translate", "extract"]
    text: str = Field(min_length=1, max_length=10_000)
    shared: bool = False


def prompt_out(prompt: SavedPrompt) -> schemas.SavedPromptOut:
    return schemas.SavedPromptOut(
        id=prompt.id,
        name=prompt.name,
        intent=prompt.intent,
        text=prompt.text,
        shared=prompt.shared,
        owner_handle=prompt.owner.handle if prompt.owner else None,
    )


@router.get("", response_model=list[schemas.SavedPromptOut])
def list_prompts(
    intent: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[schemas.SavedPromptOut]:
    """Own + shared. Anonymous callers see shared prompts only."""
    if intent is not None and intent not in PROMPT_INTENTS:
        raise api_error(
            422,
            "prompt_intent_invalid",
            f"Invalid intent '{intent}' — allowed: {', '.join(PROMPT_INTENTS)}.",
            intent=intent,
            allowed=list(PROMPT_INTENTS),
        )
    query = db.query(SavedPrompt).options(joinedload(SavedPrompt.owner))
    if user is None:
        query = query.filter(SavedPrompt.shared.is_(True))
    elif not user.is_super_admin:
        query = query.filter(or_(SavedPrompt.shared.is_(True), SavedPrompt.owner_id == user.id))
    if intent:
        query = query.filter(SavedPrompt.intent == intent)
    prompts = query.order_by(SavedPrompt.name.asc()).all()
    return [prompt_out(p) for p in prompts]


@router.post("", response_model=schemas.SavedPromptOut, status_code=201)
def create_prompt(
    payload: PromptCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> schemas.SavedPromptOut:
    prompt = SavedPrompt(
        name=payload.name.strip(),
        intent=payload.intent,
        text=payload.text,
        owner_id=user.id,
        shared=payload.shared,
    )
    db.add(prompt)
    db.commit()
    return prompt_out(prompt)


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(
    prompt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    prompt = db.get(SavedPrompt, prompt_id)
    if prompt is None:
        raise api_error(404, "prompt_not_found", "Prompt not found.", prompt_id=prompt_id)
    if not user.is_super_admin and prompt.owner_id != user.id:
        # Private prompts of others are not disclosed at all.
        if not prompt.shared:
            raise api_error(404, "prompt_not_found", "Prompt not found.", prompt_id=prompt_id)
        raise api_error(403, "prompt_owner_only", "Only the owner can delete the prompt.")
    db.delete(prompt)
    db.commit()
