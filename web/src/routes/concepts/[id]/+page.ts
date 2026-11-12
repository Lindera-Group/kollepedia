import { browser } from '$app/environment';
import { ApiError, serverApi, type ConceptOut } from '$lib/api';
import type { PageLoad } from './$types';

export type SoftReason = 'not_found' | 'error' | null;

/** SEO page: the concept head (term + definition + relations) renders
 * server-side. Concepts in org-private collections 404 anonymously — with a
 * login signal we defer to a client-side retry (reason stays null); otherwise
 * the page renders a soft not-found state (paket D). Never an error page. */
export const load: PageLoad = async ({ fetch, params, parent }) => {
  const api = serverApi(fetch);
  try {
    return {
      concept: (await api.concept(params.id)) as ConceptOut | null,
      reason: null as SoftReason
    };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      if (!browser && (await parent()).hasSession) {
        return { concept: null, reason: null as SoftReason };
      }
      return { concept: null, reason: 'not_found' as SoftReason };
    }
    return { concept: null, reason: 'error' as SoftReason };
  }
};
