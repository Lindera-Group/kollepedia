import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

/** The manual moved from /help to /manual (menu rename). Permanent redirect;
 * browsers carry the #section fragment over to the target on their own, so
 * old anchored links keep working. */
export const load: PageLoad = () => {
  redirect(301, '/manual');
};
