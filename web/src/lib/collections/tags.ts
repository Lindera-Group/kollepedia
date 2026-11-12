/** Tag-filter helpers for the collection page (iteration 3).
 *
 * The API takes a single `?tag=` — multiselect ANDs are resolved by fetching
 * with the FIRST selected tag server-side and narrowing the rest client-side
 * (documented trade-off: the local pass only sees the fetched page).
 */

/** `part:`-tags are collection subdivisions — show them as "Del N · rest". */
export function prettifyTag(tag: string): string {
  if (!tag.startsWith('part:')) return tag;
  const rest = tag.slice('part:'.length).trim();
  const match = /^(\d+)(?:[-_\s]+(.+))?$/.exec(rest);
  if (match) {
    const [, number, label] = match;
    return label ? `Del ${number} · ${label.replaceAll(/[-_]+/g, ' ')}` : `Del ${number}`;
  }
  return rest ? `Del ${rest}` : tag;
}

/** Most frequent tags first (ties alphabetically, sv), capped at `max`. */
export function topTags(tagLists: string[][], max = 14): string[] {
  const counts = new Map<string, number>();
  for (const tags of tagLists) {
    for (const tag of tags) {
      if (!tag) continue;
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'sv'))
    .slice(0, max)
    .map(([tag]) => tag);
}

/** Keep items carrying EVERY tag in `tags` (AND semantics). */
export function filterByTags<T extends { tags: string[] }>(items: T[], tags: string[]): T[] {
  if (tags.length === 0) return items;
  return items.filter((item) => tags.every((tag) => item.tags.includes(tag)));
}

/** Toggle membership, preserving selection order (first tag = server-side tag). */
export function toggleTag(selected: string[], tag: string): string[] {
  return selected.includes(tag) ? selected.filter((t) => t !== tag) : [...selected, tag];
}
