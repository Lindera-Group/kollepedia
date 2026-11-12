// SSR is ON for the public read path (SEO pages fetch in universal load
// functions via serverApi). Auth/admin pages render their shell on the
// server and fetch client-side. No prerendering — content is DB-driven.
//
// NOTE: the render language is pinned in +layout.svelte's component init, NOT
// here. Load functions of concurrent requests interleave across awaits, so a
// module-level language set here could be overwritten by another request
// before this request's tree renders; component init runs inside the
// synchronous render itself and cannot race.
import type { LayoutLoad } from './$types';

export const prerender = false;

export const load: LayoutLoad = ({ data }) => data;
