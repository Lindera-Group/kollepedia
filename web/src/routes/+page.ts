import {
  serverApi,
  type ConceptListItem,
  type ConceptListOut,
  type StatsOut
} from '$lib/api';
import { PAGE_LIMIT } from '$lib/components/infiniteList';
import type { PageLoad } from './$types';

/** SEO page: the browse list (all concepts, first page), stats and the
 * Tidsmaskinen teaser render server-side. `browse` seeds the main term list so
 * the home page is the search field + every term from the first byte. The full
 * collections list lives on /collections. API failure degrades to the inline
 * banner (no 500) — the search UI still works. */
export const load: PageLoad = async ({ fetch }) => {
  const api = serverApi(fetch);
  try {
    const [browse, stats, demo] = await Promise.all([
      api.concepts({ limit: PAGE_LIMIT }),
      api.stats(),
      api.concepts({ collection: 'tidsmaskinen', limit: 12 })
    ]);
    return {
      browse: browse as ConceptListOut | null,
      stats: stats as StatsOut | null,
      showcase: [...demo.items].sort((a, b) => b.version_count - a.version_count),
      loadError: null as string | null
    };
  } catch (e) {
    return {
      browse: null as ConceptListOut | null,
      stats: null as StatsOut | null,
      showcase: [] as ConceptListItem[],
      loadError: String(e)
    };
  }
};
