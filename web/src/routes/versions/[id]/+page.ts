import { browser } from '$app/environment';
import { ApiError, serverApi, type VersionPermalinkOut } from '$lib/api';
import type { PageLoad } from './$types';

export type SoftReason = 'not_found' | 'error' | null;

/** Citable permalink: the frozen version renders server-side. Versions in
 * org-private collections 404 anonymously — with a login signal we defer to
 * a client-side retry (reason stays null); otherwise the page renders a soft
 * not-found state (paket D). Never an error page. */
export const load: PageLoad = async ({ fetch, params, parent }) => {
  const api = serverApi(fetch);
  try {
    return {
      version: (await api.version(params.id)) as VersionPermalinkOut | null,
      reason: null as SoftReason
    };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      if (!browser && (await parent()).hasSession) {
        return { version: null, reason: null as SoftReason };
      }
      return { version: null, reason: 'not_found' as SoftReason };
    }
    return { version: null, reason: 'error' as SoftReason };
  }
};
