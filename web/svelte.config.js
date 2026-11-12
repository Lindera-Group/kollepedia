import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    // SSR for the public read path. The node server also proxies /api to the
    // FastAPI backend via src/hooks.server.ts (env API_URL) — no nginx needed.
    adapter: adapter(),

    // Content Security Policy (security review 2026-11-10, finding 3.3).
    //
    // Enforced: only the directives that cannot break the page (no framing,
    // no <base> hijack, no plugins). Everything else is Report-Only for now:
    //  - app.html has an inline theme script without `nonce="%sveltekit.nonce%"`;
    //    an enforced `script-src 'self'` would block it (theme flash) until
    //    app.html carries the nonce attribute;
    //  - Svelte transitions and `style=` attributes need 'unsafe-inline' for
    //    styles, so style-src stays permissive either way;
    //  - the policy has not run in staging yet: violations surface in the
    //    browser console and as POSTs to /csp-report (one log line each, see
    //    src/hooks.server.ts) before anything is tightened.
    // Move a directive from `reportOnly` to `directives` once staging is quiet.
    //
    // Everything loads same-origin: fonts via @fontsource (bundled), the paper
    // grain in app.css is an inline `data:` SVG (hence img-src data:), the
    // Yjs collab socket is ws(s)://<same host>/ws/collab, which 'self' covers
    // in current browsers. No third-party hosts anywhere in web/src.
    csp: {
      mode: 'auto',
      directives: {
        'frame-ancestors': ['none'],
        'base-uri': ['self'],
        'object-src': ['none']
      },
      // SvelteKit refuses a report-only policy without report-uri/report-to
      // (runtime/server/page/csp.js throws), so reports go to /csp-report.
      reportOnly: {
        'default-src': ['self'],
        'script-src': ['self'],
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:', 'blob:'],
        'font-src': ['self', 'data:'],
        'connect-src': ['self'],
        'form-action': ['self'],
        'report-uri': ['/csp-report']
      }
    }
  }
};

export default config;
