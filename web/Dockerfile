# Kollepedia NG web — SvelteKit SSR (adapter-node).
# Build context: web (compose: `build: ./web`).
#
# The node server renders the public read path server-side AND proxies
# /api + /health to the FastAPI container via src/hooks.server.ts (env
# API_URL) — nginx is gone. Compose sets API_URL, ORIGIN and (already
# defaulted below) BODY_SIZE_LIMIT; Traefik handles TLS + compression.

# ---- Stage 1: build the SvelteKit app ---------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Stage 2: node runtime ---------------------------------------------------
# adapter-node bundles devDependencies into build/ but externalises everything
# listed under "dependencies" (tiptap, yjs, y-websocket …), so those must be
# installed here too — without them every SSR route that imports them (the
# concept page via DefinitionEditor) fails with ERR_MODULE_NOT_FOUND on a hard
# load, while client-side navigation keeps working and hides the bug.
FROM node:22-alpine

WORKDIR /app

COPY --from=build /app/package.json /app/package-lock.json ./
# --ignore-scripts: the "prepare" hook (svelte-kit sync) needs devDependencies.
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force

COPY --from=build /app/build ./build

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0 \
    # Import uploads (CSV/XLSX) pass through the /api proxy — the adapter
    # default of 512K would reject them (was client_max_body_size 25m).
    BODY_SIZE_LIMIT=25M

# Run as the unprivileged user that ships with the node image.
USER node

EXPOSE 3000

# /healthz is answered locally by hooks.server.ts so this check reports the
# node server's liveness without depending on the API container.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:3000/healthz"]

CMD ["node", "build/index.js"]
