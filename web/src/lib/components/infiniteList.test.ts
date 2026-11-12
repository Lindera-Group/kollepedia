import { describe, expect, it } from 'vitest';
import { appendPage, hasMore, nextOffset, sameQuery } from './infiniteList';

describe('infinite list helpers', () => {
  it('appendPage appends new rows and drops ids already present', () => {
    const loaded = [{ id: 'a' }, { id: 'b' }];
    expect(appendPage(loaded, [{ id: 'b' }, { id: 'c' }])).toEqual([
      { id: 'a' },
      { id: 'b' },
      { id: 'c' }
    ]);
    expect(appendPage([], [{ id: 'x' }])).toEqual([{ id: 'x' }]);
  });

  it('nextOffset/hasMore walk pages and terminate on short or empty pages', () => {
    expect(nextOffset(0, 30, 95)).toBe(30);
    expect(nextOffset(90, 5, 95)).toBe(95);
    // Empty page (total shrank server-side) clamps to total — no stall loop.
    expect(nextOffset(60, 0, 95)).toBe(95);
    expect(hasMore(30, 95)).toBe(true);
    expect(hasMore(95, 95)).toBe(false);
    expect(hasMore(0, null)).toBe(false);
  });

  it('sameQuery matches shallow descriptors; null (no active query) never matches', () => {
    expect(sameQuery({ q: 'stop', lang: '' }, { q: 'stop', lang: '' })).toBe(true);
    expect(sameQuery({ q: 'stop', lang: '' }, { q: 'stop', lang: 'sv' })).toBe(false);
    expect(sameQuery(null, { q: 'stop', lang: '' })).toBe(false);
  });
});
