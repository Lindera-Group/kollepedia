# check=skip=SecretsUsedInArgOrEnv
# (^ DEV_AUTH matches BuildKit's "AUTH" secret heuristic, but it is a feature
# flag — 0/1 — not a credential. Real secrets are injected at runtime only.)
#
# Kollepedia NG server — multi-stage uv build.
# Build context: server (compose: `build: ./server`).
#
# Runtime env (see ../docs/DEPLOYMENT.md):
#   DATABASE_URL  sqlite:////app/data/kollepedia.db (default) or postgresql+psycopg://…
#   JWT_SECRET    REQUIRED in production (compose injects it from .env)
#   DEV_AUTH      0 in production (X-User dev-fallback gate; see note below)
#   CORS_ORIGINS  comma-separated allowed origins (app/main.py)

# ---- Stage 1: install dependencies with uv ---------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies only — this layer rebuilds only when the lockfile changes.
# The project is virtual (no [build-system] in pyproject.toml), so uv installs
# just the locked dependencies into /app/.venv.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---- Stage 2: runtime -------------------------------------------------------
# Same base as the uv image family, so the venv's interpreter path matches.
FROM python:3.13-slim-bookworm

WORKDIR /app

# Non-root runtime user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY scripts ./scripts
RUN chmod +x /app/scripts/docker-entrypoint.sh

# SQLite database + rotating backups live here (named volume in compose).
# Ownership is copied into a fresh named volume on first use, so it must be
# owned by `app` in the image.
RUN mkdir -p /app/data && chown -R app:app /app/data

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
# Default DB path (matches the app/db.py fallback); compose sets it explicitly.
ENV DATABASE_URL="sqlite:////app/data/kollepedia.db"
# The X-User dev fallback is off by default everywhere (app/deps.py honours it
# only when DEV_AUTH=1); stated explicitly so the image never inherits a 1.
ENV DEV_AUTH=0
# JWT_SECRET (REQUIRED: the entrypoint and app refuse to start without a
# strong value while DEV_AUTH is off) and CORS_ORIGINS come via compose/.env.

USER app
VOLUME /app/data
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8088/health', timeout=4).status == 200 else 1)"]

# Pending migrations run before the API starts (scripts/run_migrations.py),
# so staging/prod can never drift from the migration set in the image.
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
