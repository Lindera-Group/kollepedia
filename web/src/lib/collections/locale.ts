import type { CollectionLocale, CollectionOut } from '$lib/api';
import type { Lang } from '$lib/i18n.svelte';

export interface LocalizedCollection {
  name: string;
  short: string | null;
  /** Long markdown description in the requested language, or the other one. */
  description: string | null;
  /** Which language `description` actually came from (for a "shown in …" note),
   * or null when there is no localised description at all. */
  descriptionLang: Lang | null;
}

/** Resolve a collection's display fields for the UI language, falling back to
 * the other language and finally to the base (non-localised) name. The rich
 * bilingual descriptions come from migration 007 (`locales` JSON) and may be
 * absent (test collections). */
export function localizedCollection(collection: CollectionOut, lang: Lang): LocalizedCollection {
  const other: Lang = lang === 'sv' ? 'en' : 'sv';
  const locales = collection.locales ?? {};

  function pick(key: keyof CollectionLocale): { value: string | null; lang: Lang | null } {
    const here = locales[lang]?.[key];
    if (here) return { value: here, lang };
    const there = locales[other]?.[key];
    if (there) return { value: there, lang: other };
    return { value: null, lang: null };
  }

  const description = pick('description');
  return {
    name: pick('name').value ?? collection.name,
    short: pick('short_description').value,
    description: description.value,
    descriptionLang: description.lang
  };
}
