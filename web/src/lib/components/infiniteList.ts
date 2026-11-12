/** Pure helpers for accumulating infinite-scroll listings (used with
 * InfiniteSentinel.svelte on the start page and the collection page).
 * `offset` counts server rows CONSUMED — the next fetch offset. */

export const PAGE_LIMIT = 30;

/** Append `page` to `items`, dropping ids already present. Offset pagination
 * can overlap when rows are inserted/deleted between requests, and duplicate
 * ids would crash Svelte's keyed {#each}. */
export function appendPage<T extends { id: string }>(items: T[], page: T[]): T[] {
  const seen = new Set(items.map((item) => item.id));
  return [...items, ...page.filter((item) => !seen.has(item.id))];
}

/** Advance by rows RECEIVED (not rows kept after dedupe) so an overlapping
 * page still terminates; an empty page clamps straight to `total`. */
export function nextOffset(offset: number, received: number, total: number): number {
  return received === 0 ? total : offset + received;
}

/** More pages to fetch? `total === null` means no listing is active. */
export function hasMore(offset: number, total: number | null): boolean {
  return total !== null && offset < total;
}

/** Shallow equality between the active query descriptor and the one derived
 * from live filter state — a match means the accumulated items already
 * belong to these filters (the snapshot-restore no-refetch check). */
export function sameQuery<T extends Record<string, string | boolean>>(
  a: T | null,
  b: T
): boolean {
  return a !== null && Object.keys(b).every((key) => a[key] === b[key]);
}
