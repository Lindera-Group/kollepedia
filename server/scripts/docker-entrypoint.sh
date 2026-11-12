#!/bin/sh
# Apply pending NG migrations before the API starts (parity with v1's
# entrypoint). A failing migration aborts startup: better a visibly
# unhealthy container than a silently drifted database.
set -e

# Fail closed before anything else runs (the same rule as
# app/deps.py:require_strong_jwt_secret): with the X-User dev fallback off,
# a missing, dev-default or short JWT_SECRET lets anyone mint a token.
if [ "${DEV_AUTH:-0}" != "1" ]; then
  if [ -z "${JWT_SECRET:-}" ] \
    || [ "$JWT_SECRET" = "kollepedia-dev-secret-do-not-use-in-prod" ] \
    || [ "${#JWT_SECRET}" -lt 32 ]; then
    echo "JWT_SECRET must be set to a strong value when DEV_AUTH is off" >&2
    exit 1
  fi
fi

cd /app
python scripts/run_migrations.py
exec "$@"
