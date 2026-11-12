/** Server hooks: same-origin /api gateway (nginx replacement).
 *
 * The adapter-node server sits directly behind Traefik and proxies
 * /api/* + /health to the FastAPI container (env API_URL, default
 * http://localhost:8088 for local dev). This keeps the SPA and API
 * same-origin (cookies, no CORS) with one less container.
 *
 * SSR load functions also come through here: SvelteKit's `event.fetch`
 * resolves relative '/api/v1/…' URLs through this handle hook, so
 * `serverApi` needs no absolute base URL.
 */
import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const apiOrigin = (): string => env.API_URL ?? 'http://localhost:8088';

/** Headers that must not be forwarded through a proxy (plus host — the
 * upstream sees its own), accept-encoding (fetch negotiates its own, and
 * re-sending the client's breaks body decoding on the way back),
 * x-forwarded-for (the proxy sets it itself below, from getClientAddress(),
 * as the single value the API reads for rate limiting and audit) and x-user
 * (the DEV_AUTH=1 identity header; a client must never be able to supply it). */
const SKIP_REQUEST_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'accept-encoding',
  'content-length',
  'x-forwarded-for',
  'x-user'
]);

/** Upstream response headers dropped because fetch already decoded the body
 * (content-encoding/-length would lie) or they are hop-by-hop. */
const SKIP_RESPONSE_HEADERS = new Set([
  'content-encoding',
  'content-length',
  'transfer-encoding',
  'connection',
  'keep-alive'
]);

export const handle: Handle = async ({ event, resolve }) => {
  const { pathname, search } = event.url;

  // Container-local liveness for the Docker HEALTHCHECK — never touches the API.
  if (pathname === '/healthz') {
    return new Response('ok\n', { headers: { 'content-type': 'text/plain' } });
  }

  // Receiver for Content-Security-Policy-Report-Only (kit.csp.reportOnly in
  // svelte.config.js). One log line per report so violations surface in the
  // container log before the policy is enforced; nothing is stored.
  if (pathname === '/csp-report') {
    return cspReport(event.request);
  }

  // /health proves the whole chain (Traefik → node → FastAPI) for the deploy
  // workflows' verify step; /api/v1/* is the actual API surface.
  if (pathname === '/health' || pathname.startsWith('/api/')) {
    return proxyToApi(event, pathname + search);
  }

  // Keep the served <html lang> in step with the cookie language the app
  // renders in (app.html hardcodes sv, the default). English visitors get
  // lang="en" for screen readers and crawlers.
  if (event.cookies.get('kollepedia-lang') === 'en') {
    return resolve(event, {
      transformPageChunk: ({ html }) => html.replace('<html lang="sv"', '<html lang="en"')
    });
  }

  return resolve(event);
};

/** Log a CSP violation report (`application/csp-report` JSON) and answer 204.
 * Only a handful of fields are kept, JSON-encoded and length-capped, and URL
 * fields lose their query string and fragment, so neither raw client text nor
 * a token from a reset or verification page reaches the log. Malformed bodies
 * are ignored. */
async function cspReport(request: Request): Promise<Response> {
  if (request.method !== 'POST') {
    return new Response(null, { status: 405, headers: { allow: 'POST' } });
  }
  try {
    const body = JSON.parse((await request.text()).slice(0, 16_384)) as Record<string, unknown>;
    const report = (body['csp-report'] ?? body) as Record<string, unknown>;
    const fields = [
      'document-uri',
      'violated-directive',
      'effective-directive',
      'blocked-uri',
      'source-file',
      'line-number'
    ];
    // URL fields are reduced to origin + path: a report from /reset?token=…
    // or /verify-email?token=… must never put the token in the log.
    const URL_FIELDS = new Set(['document-uri', 'blocked-uri', 'source-file']);
    const clean = (k: string, v: unknown): string => {
      const text = String(v).slice(0, 300);
      if (!URL_FIELDS.has(k)) return text;
      try {
        const u = new URL(text);
        return `${u.origin}${u.pathname}`;
      } catch {
        return text.split(/[?#]/)[0];
      }
    };
    const picked = Object.fromEntries(
      fields.filter((k) => k in report).map((k) => [k, clean(k, report[k])])
    );
    console.warn('[csp-report]', JSON.stringify(picked));
  } catch {
    /* not a CSP report – ignore */
  }
  return new Response(null, { status: 204 });
}

async function proxyToApi(
  event: Parameters<Handle>[0]['event'],
  pathAndQuery: string
): Promise<Response> {
  const { request } = event;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!SKIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  // Forwarding metadata (nginx parity). The client's own x-forwarded-for is
  // skipped above, so the API only ever sees the one address we set here.
  // getClientAddress() can throw for internal SSR sub-requests — fall back
  // quietly (no header at all rather than a client-supplied one).
  try {
    headers.set('x-forwarded-for', event.getClientAddress());
  } catch {
    /* internal request — no client socket */
  }
  headers.set('x-forwarded-proto', event.url.protocol.replace(':', ''));
  headers.set('x-forwarded-host', event.url.host);

  // Buffer the body (imports are capped by BODY_SIZE_LIMIT, 25M in deploys) —
  // streaming request bodies over undici would need duplex plumbing.
  const body =
    request.method === 'GET' || request.method === 'HEAD'
      ? undefined
      : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(apiOrigin() + pathAndQuery, {
      method: request.method,
      headers,
      body,
      redirect: 'manual'
    });
  } catch {
    return new Response(JSON.stringify({ detail: 'API unavailable' }), {
      status: 502,
      headers: { 'content-type': 'application/json' }
    });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!SKIP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });
  // set-cookie folds into one comma-joined value via forEach — re-append the
  // real ones individually (the auth refresh cookie travels this path).
  const setCookies = upstream.headers.getSetCookie?.() ?? [];
  if (setCookies.length > 0) {
    responseHeaders.delete('set-cookie');
    for (const cookie of setCookies) responseHeaders.append('set-cookie', cookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders
  });
}
