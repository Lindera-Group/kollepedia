"""Structured API errors (plan NG_ATTRIBUTION_OCH_FELHANTERING, paket E1).

Every user-facing error carries a machine-readable ``code`` that the web
client maps to a localized message (``apierr.<code>`` i18n keys). ``message``
is the English fallback for API consumers, logs and tests — the UI must never
render it. Interpolation values go in ``params`` — never baked into the code
and never load-bearing in the message text.

Wire shape: ``{"detail": {"code": ..., "message": ..., "params": {...}}}``.
The params object is omitted when empty so simple errors stay simple.
"""

from typing import Any

from fastapi import HTTPException


def api_error(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    **params: Any,
) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if params:
        detail["params"] = params
    return HTTPException(status_code=status_code, detail=detail, headers=headers)
