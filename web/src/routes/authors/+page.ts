import { serverApi } from '$lib/api';
import type { PageLoad } from './$types';

/** SEO page: the full (unfiltered) author directory renders server-side.
 * The search box narrows client-side. A failed load is a soft in-page
 * state (paket D), never an error page. */
export const load: PageLoad = async ({ fetch }) => {
  const api = serverApi(fetch);
  try {
    return { authors: await api.authors('', 200) };
  } catch {
    return { authors: null };
  }
};
