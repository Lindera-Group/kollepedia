import { browser } from '$app/environment';
import { ApiError, serverApi, type ConceptGraphOut } from '$lib/api';
import type { PageLoad } from './$types';

export type SoftReason = 'not_found' | 'error' | null;

/** Time Machine: the full version graph renders server-side (the playback
 * chrome hydrates on the client). Same org-private 404 deferral as the
 * concept page; a hard not-found renders a soft in-page state (paket D). */
export const load: PageLoad = async ({ fetch, params, parent }) => {
  const api = serverApi(fetch);
  try {
    return {
      graph: (await api.graph(params.id)) as ConceptGraphOut | null,
      reason: null as SoftReason
    };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      if (!browser && (await parent()).hasSession) {
        return { graph: null, reason: null as SoftReason };
      }
      return { graph: null, reason: 'not_found' as SoftReason };
    }
    return { graph: null, reason: 'error' as SoftReason };
  }
};
