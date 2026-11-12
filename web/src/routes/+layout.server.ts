import type { LayoutServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import type { Lang } from '$lib/i18n.svelte';
import { featuresFromEnv } from '$lib/features';

/** SSR renders anonymously (the Bearer token lives in localStorage), so a 404
 * from the API can mean either "missing" or "org-private". The httpOnly
 * refresh cookie is the one server-visible login signal: page loads use it to
 * decide between a hard 404 (anonymous visitor / crawler) and deferring to a
 * client-side retry with the real session.
 *
 * `lang` comes from the same cookie the client persists, so the server renders
 * every page — including {@html} content that Svelte will not re-render on
 * hydration — in the visitor's chosen language. */
export const load: LayoutServerLoad = ({ cookies }) => {
  const lang: Lang = cookies.get('kollepedia-lang') === 'en' ? 'en' : 'sv';
  return {
    hasSession: Boolean(cookies.get('kollepedia_refresh')),
    lang,
    features: featuresFromEnv(env)
  };
};
