"""AI draft endpoint — BYOK, personal-key path (VISION §5.1).

SECURITY: the user's LLM API key arrives in the `X-LLM-Key` header, is used
for exactly one outbound provider call, and is NEVER logged, persisted, or
echoed into responses/exceptions. Do not add logging of headers or request
bodies in this module.

Providers (iteration 4): `X-LLM-Provider: anthropic | berget | openai`. Anthropic
uses the Messages API; berget/openai speak the OpenAI chat-completions format
(`POST {base}/chat/completions`, `Authorization: Bearer <key>`), with the
base URL overridable via `X-LLM-Base-URL` for other OpenAI-compatible hosts.

SSRF guard (2026-11-10): the server POSTs to whatever `X-LLM-Base-URL` names,
from inside the deployment network, so the override is accepted only for
https URLs whose host is a public DNS name resolving exclusively to global
addresses — never IP literals, localhost/.local/.internal names or private,
loopback, link-local or container ranges. A rejected URL is a 400 that says
nothing about what (if anything) answered there.

Both endpoints require a writable account (`ensure_actor_can_write`): the
proxy is BYOK, but accounts pending review get no write-adjacent surface.

The endpoint returns a DRAFT only — the UI writes the resulting version
through the normal `POST /concepts/{id}/versions` path so every write goes
through the one graph service.
"""

import ipaddress
import json
import os
import re
import socket
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session, aliased

from .. import schemas
from ..db import get_db
from ..deps import can_view_collection, ensure_actor_can_write, require_user
from ..errors import api_error
from ..features import require_feature
from ..models import Concept, SavedPrompt, User, Version, VersionEdge
from .imports import COLUMNS as IMPORT_COLUMNS

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(require_feature("ai"))])

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOKENS = 1500
EXTRACT_MAX_TOKENS = 8000
MAX_EXTRACT_CHARS = 50_000
TIMEOUT_S = 60.0
GLOSSARY_LIMIT = 15

# OpenAI-compatible providers (iteration 4).
OPENAI_COMPATIBLE_BASE_URLS = {
    "berget": "https://api.berget.ai/v1",
    "openai": "https://api.openai.com/v1",
}
BERGET_FALLBACK_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.2
PROVIDERS = ("anthropic", "berget", "openai")

# Hostname suffixes that only ever name something on our side of the proxy.
BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", "localhost")


def _rejected_base_url() -> Exception:
    """One generic 400 for every rejection reason: the message must not help
    a caller map what is reachable from inside the deployment."""
    return api_error(
        400,
        "ai_base_url_rejected",
        "X-LLM-Base-URL must be an https URL to a public host name.",
    )


def validate_base_url(raw: str) -> str:
    """Return the base URL if it may be used as an outbound target, else raise
    `ai_base_url_rejected`. Accepted: scheme https, a DNS host name (no IP
    literal, no localhost/.local/.internal/.localhost suffix) and every
    address the resolver returns is global. Resolution happens here, before
    the request, so a name pointing at a container or loopback address is
    stopped without any connection being attempted."""
    url = raw.strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        raise _rejected_base_url() from None
    host = (parts.hostname or "").strip().rstrip(".").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise _rejected_base_url()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # a name, as required — literals are rejected below
    else:
        raise _rejected_base_url()
    if host.endswith(BLOCKED_HOST_SUFFIXES):
        raise _rejected_base_url()
    try:
        # `.port` raises ValueError on a malformed port — rejected like the rest.
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OverflowError, ValueError):
        raise _rejected_base_url() from None
    addresses = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            raise _rejected_base_url() from None
    if not addresses or not all(address.is_global for address in addresses):
        raise _rejected_base_url()
    return url


def _normalise_provider(raw: str) -> str:
    provider = raw.strip().lower()
    if provider not in PROVIDERS:
        raise api_error(
            400,
            "ai_provider_unknown",
            f"Unknown provider '{provider}' — allowed: {', '.join(PROVIDERS)}",
            provider=provider,
            allowed=list(PROVIDERS),
        )
    return provider


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return DEFAULT_MODEL
    if provider == "berget":
        return os.getenv("BERGET_DEFAULT_MODEL", "").strip() or BERGET_FALLBACK_MODEL
    return OPENAI_DEFAULT_MODEL


_JSON_SHAPE = (
    'Answer ONLY with a JSON object of the exact form {"canonical_form": "...", '
    '"definition_md": "...", "note_suggestion": "..."} — no markdown fences, '
    "no commentary before or after."
)

SYSTEM_TRANSLATE = (
    "You are a terminologist specialising in public transport (kollektivtrafik). "
    "You translate terminology entries between Swedish and English, preserving the "
    "conventions of the European public-transport standards (Transmodel, NeTEx, SIRI) "
    "and established Swedish sector usage. Translate the concept, not the words: pick "
    "the canonical term a domain expert would use in the target language, and render "
    "the definition idiomatically. Keep Markdown structure from the source definition. "
    "The note_suggestion is a one-sentence change note in the target language. " + _JSON_SHAPE
)

SYSTEM_SYNTHESIZE = (
    "You are a terminologist specialising in public transport (kollektivtrafik). "
    "You merge several competing definitions of the same concept into one clear, "
    "neutral Swedish definition (definition_md, Markdown) that preserves every "
    "substantive distinction the sources make, without inventing new claims. "
    "canonical_form is the best Swedish term; note_suggestion is a one-sentence "
    "Swedish change note explaining what was merged. " + _JSON_SHAPE
)


def _version_block(versions: list[Version]) -> str:
    parts = []
    for index, version in enumerate(versions, 1):
        parts.append(
            f"{index}. Term: {version.canonical_form} [{version.language}]\n"
            f"   Definition: {version.definition_md}"
        )
    return "\n".join(parts)


def _glossary_pairs(db: Session, source: Version, limit: int = GLOSSARY_LIMIT) -> list[str]:
    """Existing translation pairs in the source's collection (in-domain glossary)."""
    concept = db.get(Concept, source.concept_id)
    if concept is None:
        return []
    child = aliased(Version)
    parent = aliased(Version)
    child_concept = aliased(Concept)
    rows = (
        db.query(parent.canonical_form, parent.language, child.canonical_form, child.language)
        .select_from(VersionEdge)
        .join(child, child.id == VersionEdge.child_id)
        .join(parent, parent.id == VersionEdge.parent_id)
        .join(child_concept, child_concept.id == child.concept_id)
        .filter(
            VersionEdge.edge_type == "translated_from",
            child_concept.collection_id == concept.collection_id,
            child.language != parent.language,
        )
        .limit(limit)
        .all()
    )
    pairs = []
    for parent_form, parent_lang, child_form, child_lang in rows:
        pairs.append(f"- {parent_form} ({parent_lang}) ⇄ {child_form} ({child_lang})")
    return pairs


def _translate_prompt(
    db: Session, versions: list[Version], target_language: str, guidance: str | None
) -> str:
    sections = [
        "Translate the following terminology entry (all source versions describe "
        "the same concept).",
        "Source version(s):\n" + _version_block(versions),
        f"Target language: {target_language}",
    ]
    glossary = _glossary_pairs(db, versions[0])
    if glossary:
        sections.append(
            "Existing translation pairs in the same collection — follow their "
            "conventions:\n" + "\n".join(glossary)
        )
    if guidance:
        sections.append(f"Additional guidance: {guidance}")
    return "\n\n".join(sections)


def _synthesize_prompt(versions: list[Version], guidance: str | None) -> str:
    sections = [
        "Merge the following competing definitions of the same concept into one "
        "Swedish definition.",
        "Source versions:\n" + _version_block(versions),
    ]
    if guidance:
        sections.append(f"Additional guidance: {guidance}")
    return "\n\n".join(sections)


def _call_anthropic(
    *, key: str, model: str, system: str, user_content: str, max_tokens: int = MAX_TOKENS
) -> str:
    """One Messages API call. The key lives only in this request's headers —
    never in logs, exception messages, or return values."""
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    try:
        response = httpx.post(
            ANTHROPIC_MESSAGES_URL, json=body, headers=headers, timeout=TIMEOUT_S
        )
    except httpx.HTTPError as exc:
        # Exception class name only — httpx errors can embed request details.
        raise api_error(
            502,
            "ai_unavailable",
            f"AI provider unreachable ({type(exc).__name__})",
            error=type(exc).__name__,
        ) from None
    if response.status_code != 200:
        message = f"AI provider error (HTTP {response.status_code})"
        params: dict[str, Any] = {"http_status": response.status_code}
        try:
            error = response.json().get("error", {})
            if isinstance(error, dict) and error.get("type"):
                message += f": {error['type']}"
                params["error_type"] = error["type"]
        except ValueError:
            pass
        code = "ai_rate_limited" if response.status_code == 429 else "ai_provider_error"
        raise api_error(502, code, message, **params)
    try:
        data = response.json()
        blocks = data.get("content", [])
        text = "".join(
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
    except (ValueError, AttributeError):
        raise api_error(
            502, "ai_response_unreadable", "AI provider returned an unreadable response"
        ) from None
    if not text.strip():
        raise api_error(502, "ai_response_empty", "AI provider returned an empty draft")
    return text


def _call_openai_compatible(
    *,
    key: str,
    base_url: str,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """One chat-completions call (berget/openai/any compatible host). The key
    lives only in this request's Authorization header — never in logs,
    exception messages, or return values."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": OPENAI_TEMPERATURE,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        response = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        # Exception class name only — httpx errors can embed request details.
        raise api_error(
            502,
            "ai_unavailable",
            f"AI provider unreachable ({type(exc).__name__})",
            error=type(exc).__name__,
        ) from None
    if response.status_code != 200:
        error_message = f"AI provider error (HTTP {response.status_code})"
        params: dict[str, Any] = {"http_status": response.status_code}
        try:
            error = response.json().get("error", {})
            if isinstance(error, dict) and error.get("type"):
                error_message += f": {error['type']}"
                params["error_type"] = error["type"]
        except ValueError:
            pass
        code = "ai_rate_limited" if response.status_code == 429 else "ai_provider_error"
        raise api_error(502, code, error_message, **params)
    try:
        data = response.json()
        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        text = message.get("content") or ""
        if not isinstance(text, str):
            text = ""
    except (ValueError, AttributeError, IndexError, TypeError):
        raise api_error(
            502, "ai_response_unreadable", "AI provider returned an unreadable response"
        ) from None
    if not text.strip():
        raise api_error(502, "ai_response_empty", "AI provider returned an empty draft")
    return text


def _call_provider(
    *,
    provider: str,
    key: str,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = MAX_TOKENS,
    base_url: str | None = None,
) -> str:
    """Dispatch to the provider adapter. base_url (X-LLM-Base-URL) overrides
    the built-in host for OpenAI-compatible providers — only after
    validate_base_url has accepted it (SSRF guard, see module docstring)."""
    if provider == "anthropic":
        return _call_anthropic(
            key=key, model=model, system=system, user_content=user_content, max_tokens=max_tokens
        )
    override = (base_url or "").strip()
    target = validate_base_url(override) if override else OPENAI_COMPATIBLE_BASE_URLS[provider]
    return _call_openai_compatible(
        key=key,
        base_url=target,
        model=model,
        system=system,
        user_content=user_content,
        max_tokens=max_tokens,
    )


def _resolve_prompt(db: Session, prompt_id: str | None, user: User | None) -> SavedPrompt | None:
    """A saved prompt is usable when it is shared or owned by the caller."""
    if not prompt_id:
        return None
    prompt = db.get(SavedPrompt, prompt_id)
    if prompt is None or not (
        prompt.shared or (user is not None and (user.is_super_admin or prompt.owner_id == user.id))
    ):
        raise api_error(
            400, "prompt_not_found", f"Unknown prompt {prompt_id}", prompt_id=prompt_id
        )
    return prompt


def _parse_draft(text: str, fallback_form: str) -> dict[str, str]:
    """Parse the model's JSON answer robustly: strip code fences, tolerate
    surrounding prose; fall back to raw text as definition_md."""
    cleaned = text.strip()
    fence = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*?)\n?```\s*$", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    data: Any = None
    try:
        data = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if 0 <= start < end:
            try:
                data = json.loads(cleaned[start : end + 1])
            except ValueError:
                data = None
    if not isinstance(data, dict):
        return {
            "canonical_form": fallback_form,
            "definition_md": text.strip(),
            "note_suggestion": "",
        }
    return {
        "canonical_form": str(data.get("canonical_form") or fallback_form),
        "definition_md": str(data.get("definition_md") or data.get("definition") or cleaned),
        "note_suggestion": str(data.get("note_suggestion") or ""),
    }


@router.post("/draft", response_model=schemas.AiDraftOut)
def ai_draft(
    payload: schemas.AiDraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    x_llm_key: str | None = Header(default=None),
    x_llm_provider: str = Header(default="anthropic"),
    x_llm_base_url: str | None = Header(default=None),
) -> schemas.AiDraftOut:
    ensure_actor_can_write(user)
    if not x_llm_key or not x_llm_key.strip():
        raise api_error(400, "ai_key_missing", "Missing X-LLM-Key header")
    provider = _normalise_provider(x_llm_provider)
    if not payload.version_ids:
        raise api_error(400, "version_ids_required", "version_ids must not be empty")

    versions: list[Version] = []
    for version_id in payload.version_ids:
        version = db.get(Version, version_id)
        # Never send definition text the caller may not read to the LLM —
        # org_private stays 404, not disclosed (säkerhetsfix 2026-07-15).
        if version is None or not can_view_collection(user, version.concept.collection):
            raise api_error(
                400,
                "version_not_found",
                f"Unknown version {version_id}",
                version_id=version_id,
            )
        versions.append(version)

    # Saved prompt (iteration 4): its text leads the guidance; the id is echoed
    # back so the frontend can stamp it into the version's provenance.
    prompt = _resolve_prompt(db, payload.prompt_id, user)
    guidance = payload.guidance
    if prompt is not None:
        guidance = f"{prompt.text}\n\n{guidance}" if guidance else prompt.text

    model = payload.model or _default_model(provider)
    if payload.intent == "translate":
        target = payload.target_language or ("en" if versions[0].language == "sv" else "sv")
        system = SYSTEM_TRANSLATE
        user_content = _translate_prompt(db, versions, target, guidance)
    else:
        system = SYSTEM_SYNTHESIZE
        user_content = _synthesize_prompt(versions, guidance)

    text = _call_provider(
        provider=provider,
        key=x_llm_key.strip(),
        model=model,
        system=system,
        user_content=user_content,
        base_url=x_llm_base_url,
    )
    draft = _parse_draft(text, fallback_form=versions[0].canonical_form)
    return schemas.AiDraftOut(
        **draft, model=model, provider=provider, prompt_id=prompt.id if prompt else None
    )


# ── /ai/extract — BYOK extraction of unstructured glossaries (Iteration 2) ──

SYSTEM_EXTRACT = (
    "You are a terminologist specialising in public transport (kollektivtrafik). "
    "You extract terminology entries from unstructured Swedish or English glossary "
    "text. Answer ONLY with a JSON array of objects — no markdown fences, no "
    "commentary. Allowed keys per object (all values are strings): "
    + ", ".join(IMPORT_COLUMNS)
    + ". canonical_form and definition are required; keep the definition faithful "
    "to the source text, in the source language. language is 'sv' or 'en'. "
    "Join multiple tags or variants with ';'. When the text says 'se även', "
    "'jfr', 'see also' or similar, put those canonical forms (';'-joined) in "
    "related_to. Use translation_of only when the text explicitly gives an "
    "equivalent in the other language. Omit keys you have no value for. "
    "Never invent entries that are not in the text."
)


class AiExtractIn(BaseModel):
    text: str
    language: Literal["sv", "en"] | None = None


class AiExtractOut(BaseModel):
    rows: list[dict[str, str]]


def _parse_rows(text: str) -> list[dict[str, str]]:
    """Parse the model's answer into import rows: strip fences, tolerate an
    object-with-rows wrapper, coerce values to trimmed strings."""
    cleaned = text.strip()
    fence = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*?)\n?```\s*$", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    data: Any = None
    try:
        data = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if 0 <= start < end:
            try:
                data = json.loads(cleaned[start : end + 1])
            except ValueError:
                data = None
    if isinstance(data, dict):
        data = data.get("rows")
    if not isinstance(data, list):
        raise api_error(
            502,
            "ai_extract_parse_failed",
            "The AI answer could not be parsed as JSON rows.",
        )
    rows: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        row: dict[str, str] = {}
        for column in IMPORT_COLUMNS:
            value = item.get(column)
            if value is None:
                continue
            if isinstance(value, list):
                value = ";".join(str(part) for part in value)
            text_value = str(value).strip()
            if text_value:
                row[column] = text_value
        if row.get("canonical_form"):
            rows.append(row)
    return rows


@router.post("/extract", response_model=AiExtractOut)
def ai_extract(
    payload: AiExtractIn,
    user: User = Depends(require_user),
    x_llm_key: str | None = Header(default=None),
    x_llm_provider: str = Header(default="anthropic"),
    x_llm_base_url: str | None = Header(default=None),
) -> AiExtractOut:
    ensure_actor_can_write(user)
    if not x_llm_key or not x_llm_key.strip():
        raise api_error(400, "ai_key_missing", "Missing X-LLM-Key header")
    provider = _normalise_provider(x_llm_provider)
    if not payload.text.strip():
        raise api_error(400, "text_required", "text must not be empty")
    if len(payload.text) > MAX_EXTRACT_CHARS:
        raise api_error(
            400,
            "text_too_long",
            f"Text is too long ({len(payload.text)} characters, max {MAX_EXTRACT_CHARS}).",
            length=len(payload.text),
            max=MAX_EXTRACT_CHARS,
        )

    sections = ["Extract the terminology entries from the following text."]
    if payload.language:
        sections.append(f"The text is primarily in language: {payload.language}")
    sections.append(payload.text)
    answer = _call_provider(
        provider=provider,
        key=x_llm_key.strip(),
        model=_default_model(provider),
        system=SYSTEM_EXTRACT,
        user_content="\n\n".join(sections),
        max_tokens=EXTRACT_MAX_TOKENS,
        base_url=x_llm_base_url,
    )
    return AiExtractOut(rows=_parse_rows(answer))
