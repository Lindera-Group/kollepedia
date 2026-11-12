"""Feature flags, driven by the environment.

Unfinished functionality ships dark: the server refuses its endpoints and the
web (web/src/lib/features.ts, same variable names) hides its UI until the flag
is on. A flag is on when its variable is one of 1 / true / yes / on.

    FEATURE_AI   AI drafts (/ai/*) and saved prompts (/prompts).  Default off.
"""

import os
from collections.abc import Callable

from .errors import api_error

FLAGS: dict[str, str] = {"ai": "FEATURE_AI"}
_ON = {"1", "true", "yes", "on"}


def enabled(name: str) -> bool:
    return os.getenv(FLAGS[name], "").strip().lower() in _ON


def features() -> dict[str, bool]:
    """Every flag with its current state — what GET /features returns."""
    return {name: enabled(name) for name in FLAGS}


def require_feature(name: str) -> Callable[[], None]:
    """Router-level dependency: 404 `feature_disabled` while the flag is off,
    before any other dependency (auth, body) is even looked at."""

    def dependency() -> None:
        if not enabled(name):
            raise api_error(
                404,
                "feature_disabled",
                f"The '{name}' feature is disabled on this server.",
                feature=name,
            )

    return dependency
