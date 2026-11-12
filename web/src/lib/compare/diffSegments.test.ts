import { describe, expect, it } from 'vitest';
import { buildDiffSegments } from './diffSegments';

describe('buildDiffSegments', () => {
  it('yields a single eq segment for identical texts', () => {
    const segments = buildDiffSegments('en hållplats för resenärer', 'en hållplats för resenärer');
    expect(segments.map((s) => s.type)).toEqual(['eq']);
  });

  it('marks base-only words as del and column-only words as ins', () => {
    const segments = buildDiffSegments('fordonet stannar vid hållplatsen', 'fordonet stannar vid stationen');
    const del = segments.filter((s) => s.type === 'del');
    const ins = segments.filter((s) => s.type === 'ins');
    expect(del.map((s) => s.text.trim())).toEqual(['hållplatsen']);
    expect(ins.map((s) => s.text.trim())).toEqual(['stationen']);
  });

  it('treats an empty base as pure insertion', () => {
    const segments = buildDiffSegments('', 'helt ny definition');
    expect(segments.map((s) => s.type)).toEqual(['ins']);
    expect(segments[0].text).toBe('helt ny definition');
  });

  it('reconstructs the column text from eq + ins segments', () => {
    const base = 'En hållplats är en plats där fordon stannar.';
    const other = 'En station är en anläggning där tåg stannar och vänder.';
    const rebuilt = buildDiffSegments(base, other)
      .filter((s) => s.type !== 'del')
      .map((s) => s.text)
      .join('');
    expect(rebuilt.replace(/\s+/g, ' ').trim()).toBe(other);
  });
});
