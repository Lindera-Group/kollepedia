/** Slugify Swedish text for URLs, handles and collection slugs: transliterate
 * å/ä/ö/é to ASCII, lowercase, then collapse every other run to single
 * hyphens and trim. Shared by /orgs and /new-collection so the two stay
 * identical. */
export function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      /* i18n-exempt-start: Swedish→ASCII transliteration, not user-facing copy */
      .replaceAll('å', 'a')
      .replaceAll('ä', 'a')
      .replaceAll('ö', 'o')
      .replaceAll('é', 'e')
      /* i18n-exempt-end */
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
  );
}
