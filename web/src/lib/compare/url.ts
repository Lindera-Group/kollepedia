/** Pure helpers for the comparison workbench's shareable URL (/compare?ids=a,b,c). */

/** Parse the `ids` query parameter: comma-separated, trimmed, deduplicated. */
export function parseIds(param: string | null | undefined): string[] {
  if (!param) return [];
  const out: string[] = [];
  for (const raw of param.split(',')) {
    const id = raw.trim();
    if (id && !out.includes(id)) out.push(id);
  }
  return out;
}

/** Build the shareable compare URL for a set of concept ids. */
export function compareUrl(ids: string[]): string {
  if (ids.length === 0) return '/compare';
  return `/compare?ids=${ids.map(encodeURIComponent).join(',')}`;
}

/** Append an id (no-op if already present). Returns a new array. */
export function withId(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids : [...ids, id];
}

/** Remove an id. Returns a new array. */
export function withoutId(ids: string[], id: string): string[] {
  return ids.filter((x) => x !== id);
}
