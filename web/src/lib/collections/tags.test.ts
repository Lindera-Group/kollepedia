import { describe, expect, it } from 'vitest';
import { filterByTags, prettifyTag, toggleTag, topTags } from './tags';

describe('prettifyTag', () => {
  it('turns part:-tags into "Del N" with an optional readable label', () => {
    expect(prettifyTag('part:3')).toBe('Del 3');
    expect(prettifyTag('part:2-public-transport-network')).toBe('Del 2 · public transport network');
    expect(prettifyTag('part:X')).toBe('Del X');
  });

  it('leaves ordinary tags untouched', () => {
    expect(prettifyTag('hållplats')).toBe('hållplats');
    expect(prettifyTag('depart')).toBe('depart');
  });
});

describe('topTags', () => {
  it('ranks by frequency, breaks ties alphabetically and caps the list', () => {
    const lists = [
      ['b', 'a'],
      ['b', 'c'],
      ['b', 'a', 'd']
    ];
    expect(topTags(lists, 3)).toEqual(['b', 'a', 'c']);
    expect(topTags([], 5)).toEqual([]);
  });
});

describe('filterByTags', () => {
  it('requires every selected tag (AND) and passes everything for empty selection', () => {
    const items = [
      { id: 1, tags: ['a', 'b'] },
      { id: 2, tags: ['a'] },
      { id: 3, tags: ['b', 'a', 'c'] }
    ];
    expect(filterByTags(items, ['a', 'b']).map((i) => i.id)).toEqual([1, 3]);
    expect(filterByTags(items, [])).toHaveLength(3);
  });
});

describe('toggleTag', () => {
  it('adds at the end and removes without disturbing selection order', () => {
    expect(toggleTag([], 'a')).toEqual(['a']);
    expect(toggleTag(['a'], 'b')).toEqual(['a', 'b']);
    expect(toggleTag(['a', 'b'], 'a')).toEqual(['b']);
  });
});
