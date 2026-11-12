import { describe, expect, it } from 'vitest';
import { compareUrl, parseIds, withId, withoutId } from './url';

describe('parseIds', () => {
  it('returns empty for missing or blank params', () => {
    expect(parseIds(null)).toEqual([]);
    expect(parseIds(undefined)).toEqual([]);
    expect(parseIds('')).toEqual([]);
    expect(parseIds(' , ,')).toEqual([]);
  });

  it('splits, trims and deduplicates while preserving order', () => {
    expect(parseIds('a, b ,a,,c')).toEqual(['a', 'b', 'c']);
  });
});

describe('compareUrl', () => {
  it('round-trips through parseIds', () => {
    const ids = ['a1', 'b2', 'c3'];
    const url = new URL(compareUrl(ids), 'http://x');
    expect(url.pathname).toBe('/compare');
    expect(parseIds(url.searchParams.get('ids'))).toEqual(ids);
  });

  it('omits the query when there are no ids', () => {
    expect(compareUrl([])).toBe('/compare');
  });
});

describe('withId / withoutId', () => {
  it('appends only new ids and never mutates the input', () => {
    const ids = ['a', 'b'];
    expect(withId(ids, 'c')).toEqual(['a', 'b', 'c']);
    expect(withId(ids, 'a')).toEqual(['a', 'b']);
    expect(ids).toEqual(['a', 'b']);
  });

  it('removes an id and leaves others intact', () => {
    expect(withoutId(['a', 'b', 'c'], 'b')).toEqual(['a', 'c']);
    expect(withoutId(['a'], 'x')).toEqual(['a']);
  });
});
