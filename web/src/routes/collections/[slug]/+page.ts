import { browser } from '$app/environment';
import { ApiError, serverApi, type CollectionOut, type ConceptListOut } from '$lib/api';
import { topTags } from '$lib/collections/tags';
import type { PageLoad } from './$types';

const LIMIT = 30;

export type SoftReason = 'not_found' | 'error' | null;

/** SEO page: collection metadata + the first concept page render server-side.
 * One 100-item sample feeds both the initial grid (first 30) and the tag
 * chips. Org-private collections 404 anonymously — with a login signal
 * (refresh cookie) we return nulls and let the client retry with the real
 * session; otherwise the page renders a soft not-found state (paket D). */
export const load: PageLoad = async ({ fetch, params, parent }) => {
  const api = serverApi(fetch);
  try {
    const [collection, sample] = await Promise.all([
      api.collection(params.slug),
      api.concepts({ collection: params.slug, limit: 100 })
    ]);
    return {
      collection: collection as CollectionOut | null,
      concepts: {
        items: sample.items.slice(0, LIMIT),
        total: sample.total
      } as ConceptListOut | null,
      tagPool: topTags(sample.items.map((item) => item.tags)),
      reason: null as SoftReason
    };
  } catch (e) {
    const empty = { collection: null, concepts: null, tagPool: [] as string[] };
    if (e instanceof ApiError && e.status === 404) {
      if (!browser && (await parent()).hasSession) {
        return { ...empty, reason: null as SoftReason };
      }
      return { ...empty, reason: 'not_found' as SoftReason };
    }
    return { ...empty, reason: 'error' as SoftReason };
  }
};
