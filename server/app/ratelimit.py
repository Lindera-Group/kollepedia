"""Tiny in-memory sliding-window rate limiter (iteration 3).

Keyed on (client IP, route class). Route classes and their default limits
per 60-second window:

- "auth" → 10/min  (env RATE_LIMIT_AUTH)
- "ai"   → 20/min  (env RATE_LIMIT_AI)

Limits are read from the environment on every check so tests (and ops) can
tune them at runtime. `reset()` clears all counters — tests call it between
cases so one test's traffic never trips another's limit.

In-memory by design: single-process dev/small deployments. A multi-worker
deployment would swap this for a shared store behind the same interface.

`client_ip` is the one place the caller's address is derived (rate limiting
and the registration velocity heuristic share it). In deployments the API sits
behind Traefik and the SSR proxy, so the socket peer is always the web
container; the LAST `X-Forwarded-For` value is the one the nearest proxy
appended and therefore the only one a client cannot choose.
"""

import os
import threading
import time
from collections import defaultdict, deque

from starlette.requests import Request

WINDOW_SECONDS = 60.0


def client_ip(request: Request) -> str:
    """The caller's address for keying: the last X-Forwarded-For entry when
    the header is present (written by the trusted proxy in front of us),
    otherwise the socket peer. Never the first entry — that is client-supplied."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


DEFAULT_LIMITS = {"auth": 10, "ai": 20}

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def limit_for(route_class: str) -> int:
    """Requests allowed per window for a route class (env-tunable)."""
    raw = os.getenv(f"RATE_LIMIT_{route_class.upper()}", "")
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_LIMITS.get(route_class, 60)


def check(client_ip: str, route_class: str) -> int | None:
    """Record a hit. Returns None when allowed, else whole seconds to wait
    (suitable for a Retry-After header)."""
    now = time.monotonic()
    with _lock:
        window = _hits[(client_ip, route_class)]
        cutoff = now - WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= limit_for(route_class):
            return max(1, int(window[0] + WINDOW_SECONDS - now) + 1)
        window.append(now)
        return None


def reset() -> None:
    """Clear all counters (test hook)."""
    with _lock:
        _hits.clear()
