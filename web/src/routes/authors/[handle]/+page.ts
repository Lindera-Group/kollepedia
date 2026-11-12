import { ApiError, serverApi } from '$lib/api';
import type { PageLoad } from './$types';

/** SEO page: the author profile renders server-side. An unknown or hidden
 * handle is NOT an error page (paket D) — the page renders a soft
 * "no public profile" state instead, so an author link never dead-ends. */
export const load: PageLoad = async ({ fetch, params }) => {
  const api = serverApi(fetch);
  try {
    return { author: await api.author(params.handle), handle: params.handle, reason: null };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return { author: null, handle: params.handle, reason: 'not_found' as const };
    }
    return { author: null, handle: params.handle, reason: 'error' as const };
  }
};
