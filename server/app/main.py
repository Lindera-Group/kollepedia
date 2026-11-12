"""Kollepedia NG API."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Route

from . import deps, mcp_public, ratelimit, realtime
from .db import engine
from .models import Base
from .routers import (
    admin_users,
    ai,
    auth,
    authors_admin,
    collab,
    collections,
    concepts,
    endorsements,
    exports,
    imports,
    lists,
    meta,
    orgs,
    prompts,
    proposals,
    relations,
    taxonomies,
    versions,
)

logger = logging.getLogger("kollepedia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start insecure (2026-11-10): with the X-User dev fallback off
    # this instance is presumably real, so a missing/dev/short JWT_SECRET is
    # fatal, not a warning — checked before the schema is touched.
    deps.require_strong_jwt_secret()
    Base.metadata.create_all(bind=engine)
    # The public MCP endpoint (/mcp) needs its session manager running for the
    # app's lifetime (stateless transport, but the manager owns the task group).
    async with mcp_public.mcp.session_manager.run():
        yield


API_PREFIX = "/api/v1"

app = FastAPI(
    title="Kollepedia NG",
    description="Versioned, provenance-first terminology for public transport.",
    version="0.8.2",
    lifespan=lifespan,
    # The OpenAPI schema and the interactive docs live under the API prefix so
    # they pass through the same-origin /api proxy in web/src/hooks.server.ts
    # (only /health and /api/* are forwarded to this service in deploys) —
    # external API consumers can then discover the surface at
    # https://<host>/api/v1/openapi.json and /api/v1/docs.
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
)

# Comma-separated allowed origins; defaults to the local dev frontend.
# In production the SPA is served same-origin (nginx proxies /api), so CORS
# only matters for cross-origin API consumers — set CORS_ORIGINS accordingly.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5181,http://127.0.0.1:5181").split(
        ","
    )
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route classes for the sliding-window rate limiter (iteration 3):
# 10/min/IP for /auth/*, 20/min/IP for /ai/* (env-tunable, see app/ratelimit.py).
# Trailing slash required — a bare "/auth" prefix also matches /authors.
RATE_LIMITED_PREFIXES = (
    (f"{API_PREFIX}/auth/", "auth"),
    (f"{API_PREFIX}/ai/", "ai"),
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    for prefix, route_class in RATE_LIMITED_PREFIXES:
        if path.startswith(prefix):
            retry_after = ratelimit.check(ratelimit.client_ip(request), route_class)
            if retry_after is not None:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "För många förfrågningar – försök igen om en stund."},
                    headers={"Retry-After": str(retry_after)},
                )
            break
    return await call_next(request)


app.include_router(collections.router, prefix=API_PREFIX)
app.include_router(concepts.router, prefix=API_PREFIX)
app.include_router(relations.router, prefix=API_PREFIX)
app.include_router(endorsements.router, prefix=API_PREFIX)
app.include_router(lists.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)
app.include_router(meta.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(orgs.router, prefix=API_PREFIX)
app.include_router(imports.router, prefix=API_PREFIX)
app.include_router(authors_admin.router, prefix=API_PREFIX)

# Public, read-only MCP over Streamable HTTP (app/mcp_public.py). Traefik
# routes /mcp straight to this service, like /ws — the SSR proxy only carries
# /api and /health. An exact Route, not a Mount: a Mount answers /mcp with a
# redirect to /mcp/, which MCP clients do not follow.
app.router.routes.append(
    Route("/mcp", endpoint=mcp_public.asgi, methods=["GET", "POST", "DELETE"])
)
app.include_router(admin_users.router, prefix=API_PREFIX)
app.include_router(proposals.router, prefix=API_PREFIX)
app.include_router(collab.router, prefix=API_PREFIX)
app.include_router(prompts.router, prefix=API_PREFIX)
app.include_router(versions.router, prefix=API_PREFIX)
app.include_router(taxonomies.router, prefix=API_PREFIX)
# Realtime collab (Yjs sync relay) lives at /ws — outside API_PREFIX so the
# reverse proxy can route PathPrefix(`/ws`) straight to this service with
# websocket upgrade (see docs/DRIFT.md).
app.include_router(realtime.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
