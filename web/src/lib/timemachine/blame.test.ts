import { describe, expect, it } from 'vitest';
import { blameChain, tokenAges } from './blame';
import { tokenize } from './diff';

describe('blameChain', () => {
  const ids = ['v1', 'v2', 'v3'];
  const texts = [
    'bussen stannar vid hållplatsen',
    'bussen stannar alltid vid hållplatsen',
    'spårvagnen stannar alltid vid hållplatsen'
  ];

  it('stamps every token of the first version with v1', () => {
    const blame = blameChain(texts, ids);
    expect(blame[0]).toEqual(['v1', 'v1', 'v1', 'v1']);
  });

  it('keeps introducers for unchanged words and stamps new ones', () => {
    const blame = blameChain(texts, ids);
    const tokens2 = tokenize(texts[1]).map((t) => t.text.trim());
    expect(blame[1][tokens2.indexOf('alltid')]).toBe('v2');
    expect(blame[1][tokens2.indexOf('bussen')]).toBe('v1');

    const tokens3 = tokenize(texts[2]).map((t) => t.text.trim());
    expect(blame[2][tokens3.indexOf('spårvagnen')]).toBe('v3');
    expect(blame[2][tokens3.indexOf('alltid')]).toBe('v2');
    expect(blame[2][tokens3.indexOf('hållplatsen')]).toBe('v1');
  });

  it('aligns blame arrays with token counts', () => {
    const blame = blameChain(texts, ids);
    texts.forEach((text, i) => {
      expect(blame[i]).toHaveLength(tokenize(text).length);
    });
  });

  it('computes ages: newest 0, oldest 1', () => {
    const blame = blameChain(texts, ids);
    const ages = tokenAges(blame[2], ids, 2);
    const tokens3 = tokenize(texts[2]).map((t) => t.text.trim());
    expect(ages[tokens3.indexOf('spårvagnen')]).toBe(0);
    expect(ages[tokens3.indexOf('hållplatsen')]).toBe(1);
  });
});
