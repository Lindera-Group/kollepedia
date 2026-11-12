/** Bilingual taxonomy display (unlike tags): name = Swedish primary,
 * name_en = English (falls back to Swedish when missing). */
import type { TaxonomyValueOut } from '$lib/api';
import { i18n } from '$lib/i18n.svelte';

export function taxonomyValueName(value: Pick<TaxonomyValueOut, 'name' | 'name_en'>): string {
  return i18n.lang === 'en' && value.name_en ? value.name_en : value.name;
}
