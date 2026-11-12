import { serverApi, type CollectionOut, type StatsOut } from '$lib/api';
import type { PageLoad } from './$types';

/** Collections index (SEO): the full list with rich bilingual metadata renders
 * server-side. API failure degrades to an inline banner rather than a 500. */
export const load: PageLoad = async ({ fetch }) => {
  const api = serverApi(fetch);
  try {
    const [collections, stats] = await Promise.all([api.collections(), api.stats()]);
    return {
      collections,
      stats: stats as StatsOut | null,
      loadError: null as string | null
    };
  } catch (e) {
    return {
      collections: [] as CollectionOut[],
      stats: null as StatsOut | null,
      loadError: String(e)
    };
  }
};
