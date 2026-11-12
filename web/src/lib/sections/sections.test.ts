import { describe, expect, it } from 'vitest';

import type { AnnotationOut } from '$lib/api';

import { buildSegments, sourceCitations } from './sections';

let nextId = 0;
function ann(
  attr_type: string,
  start: number,
  end: number,
  value: Record<string, unknown> = {},
  quote: string | null = null
): AnnotationOut {
  return { id: `a${nextId++}`, attr_type, start, end, quote, value };
}

// Mirrors the migrated Ordbok shape: sections separated by "\n\n",
// author annotations sharing their section's span.
const TEXT = 'Inledning här.\n\nElbil – batteridriven.\n\nElbuss – oftast batteridriven.';
const S1 = { start: 16, end: 38 }; // "Elbil – batteridriven."
const S2 = { start: 40, end: 71 }; // "Elbuss – oftast batteridriven."

describe('buildSegments', () => {
  it('returns null when there are no section annotations', () => {
    expect(buildSegments(TEXT, [ann('variant', 0, 0, { form: 'elbilar' })])).toBeNull();
  });

  it('slices sections in start order and keeps text outside sections as intro', () => {
    const segments = buildSegments(TEXT, [
      ann('section', S2.start, S2.end, { number: '2' }), // out of order on purpose
      ann('section', S1.start, S1.end, { number: '1' })
    ]);
    expect(segments).not.toBeNull();
    expect(segments!.map((s) => [s.kind, s.number])).toEqual([
      ['intro', null],
      ['section', '1'],
      ['section', '2']
    ]);
    expect(segments![0].text).toBe('Inledning här.\n\n');
    expect(segments![1].text).toBe('Elbil – batteridriven.');
    expect(segments![2].text).toBe('Elbuss – oftast batteridriven.');
  });

  it('treats section "0" as an unnumbered lead-in and keeps titles when present', () => {
    const segments = buildSegments(TEXT, [
      ann('section', 0, 14, { number: '0' }),
      ann('section', S1.start, S1.end, { number: 1, title: 'Elbil' })
    ]);
    expect(segments![0]).toMatchObject({ kind: 'section', number: null, title: null });
    expect(segments![1]).toMatchObject({ kind: 'section', number: '1', title: 'Elbil' });
  });

  it('attaches authors by span and deduplicates them', () => {
    const author = {
      name: 'Lina Berglund-Snodgrass',
      affiliation: 'SLU',
      web_url: 'https://example.org/lina'
    };
    const segments = buildSegments(TEXT, [
      ann('section', S1.start, S1.end, { number: '1' }),
      ann('section', S2.start, S2.end, { number: '2' }),
      ann('author', S1.start, S1.end, author),
      ann('author', S1.start, S1.end, author), // duplicate
      ann('author', S1.start, S1.end, { name: 'Redaktörerna', affiliation: null, web_url: null }),
      ann('author', S2.start, S2.end, { name: 'Fredrik Pettersson-Löfstedt' })
    ]);
    const [, s1, s2] = segments!;
    expect(s1.authors).toEqual([
      author,
      { name: 'Redaktörerna', affiliation: null, web_url: null }
    ]);
    expect(s2.authors).toEqual([
      { name: 'Fredrik Pettersson-Löfstedt', affiliation: null, web_url: null }
    ]);
  });

  it('keeps a trailing tail after the last section as intro text', () => {
    const segments = buildSegments(TEXT, [ann('section', S1.start, S1.end, { number: '1' })]);
    expect(segments!.at(-1)).toMatchObject({ kind: 'intro', text: '\n\nElbuss – oftast batteridriven.' });
  });

  it('clamps out-of-range and inverted offsets instead of crashing', () => {
    const segments = buildSegments(TEXT, [
      ann('section', -5, S1.end, { number: '1' }),
      ann('section', 9999, S2.start, { number: '2' }) // inverted + beyond end
    ]);
    expect(segments).not.toBeNull();
    expect(segments![0].text).toBe(TEXT.slice(0, S1.end));
    expect(segments![1].text).toBe(TEXT.slice(S2.start));
  });

  it('returns null on overlapping sections (caller falls back to whole text)', () => {
    expect(
      buildSegments(TEXT, [
        ann('section', 0, 30, { number: '1' }),
        ann('section', 20, 50, { number: '2' })
      ])
    ).toBeNull();
  });

  it('skips whitespace-only gaps and empty sections but still reconstructs', () => {
    const segments = buildSegments(TEXT, [
      ann('section', S1.start, S1.end, { number: '1' }),
      ann('section', 39, 39, { number: 'tom' }),
      ann('section', S2.start, S2.end, { number: '2' })
    ]);
    expect(segments!.every((s) => s.text.trim() !== '')).toBe(true);
    expect(segments!.filter((s) => s.kind === 'section')).toHaveLength(2);
  });
});

describe('sourceCitations', () => {
  it('reads text/citation/source value keys and falls back to quote', () => {
    expect(
      sourceCitations([
        ann('source_citation', 0, 0, { text: 'K2 Ordbok 2024' }),
        ann('source_citation', 0, 0, { citation: 'Transmodel EN 12896' }),
        ann('source_citation', 0, 0, { source: 'Kollektivtrafikordboken' }),
        ann('source_citation', 0, 0, {}, 'Citatkälla'),
        ann('section', 0, 5, { number: '1' }) // ignored
      ])
    ).toEqual(['K2 Ordbok 2024', 'Transmodel EN 12896', 'Kollektivtrafikordboken', 'Citatkälla']);
  });

  it('deduplicates and drops empty citations', () => {
    expect(
      sourceCitations([
        ann('source_citation', 0, 0, { text: 'K2' }),
        ann('source_citation', 0, 0, { text: 'K2' }),
        ann('source_citation', 0, 0, { text: '  ' })
      ])
    ).toEqual(['K2']);
  });
});
