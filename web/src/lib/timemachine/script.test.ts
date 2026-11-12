import { describe, expect, it } from 'vitest';
import type { VersionOut } from '$lib/api';
import { buildTransition, type WordSpan } from './script';

function version(canonical: string, definition: string, tags: string[] = []): VersionOut {
  return {
    id: 'v-' + canonical,
    concept_id: 'c1',
    branch_id: null,
    language: 'sv',
    canonical_form: canonical,
    definition_md: definition,
    status: 'draft',
    tags,
    note: null,
    provenance: {},
    created_at: '2020-01-01T00:00:00',
    created_by: null,
    annotations: [],
    endorsements: []
  };
}

const dels = (spans: WordSpan[]) => spans.filter((s) => s.type === 'del' && s.kind === 'word');
const inss = (spans: WordSpan[]) => spans.filter((s) => s.type === 'ins' && s.kind === 'word');

describe('buildTransition — sequential layout', () => {
  // Two separated edits: "snabb → långsam" early, "kvällen → natten" late.
  const a = version('term', 'en snabb buss kör genom staden varje kväll utan undantag');
  const b = version('term', 'en långsam buss kör genom staden varje natt utan undantag');

  it('plays hunks in reading order: first hunk fully resolves before the second starts', () => {
    const t = buildTransition(a, b, 'sequential');
    const [del1, del2] = dels(t.def);
    const [ins1, ins2] = inss(t.def);
    expect(del1).toBeDefined();
    expect(del2).toBeDefined();
    // Hunk 1: mark → type → collapse, all before hunk 2's mark begins.
    expect(del1.ma!).toBeLessThan(ins1.a!);
    expect(ins1.a! + ins1.span!).toBeLessThanOrEqual(del1.ca! + 1e-6);
    expect(del1.ca! + del1.cs!).toBeLessThanOrEqual(del2.ma! + 1e-6);
    expect(del2.ma!).toBeLessThan(ins2.a!);
  });

  it('keeps every window inside the master range', () => {
    const t = buildTransition(a, b, 'sequential');
    for (const s of [...dels(t.def), ...inss(t.def)]) {
      for (const value of [s.ma, s.ca, s.a].filter((x) => x !== undefined) as number[]) {
        expect(value).toBeGreaterThanOrEqual(0.03);
        expect(value).toBeLessThanOrEqual(0.95);
      }
    }
  });

  it('resolves the title before the definition', () => {
    const t = buildTransition(
      version('gammal term', 'samma definition som byts helt'),
      version('ny term', 'en annan text som ersätter allting'),
      'sequential'
    );
    const titleIns = inss(t.title);
    const defIns = inss(t.def);
    expect(titleIns.length).toBeGreaterThan(0);
    expect(defIns.length).toBeGreaterThan(0);
    const lastTitle = Math.max(...titleIns.map((s) => s.a! + s.span!));
    const firstDef = Math.min(...defIns.map((s) => s.a!));
    expect(lastTitle).toBeLessThanOrEqual(firstDef + 1e-6);
  });

  it('subdivides a hunk typing window across its words in order', () => {
    const t = buildTransition(
      version('t', 'början slutet'),
      version('t', 'början ett två tre slutet'),
      'sequential'
    );
    const words = inss(t.def);
    expect(words).toHaveLength(3);
    for (let i = 1; i < words.length; i++) {
      expect(words[i].a!).toBeGreaterThanOrEqual(words[i - 1].a! + words[i - 1].span! - 1e-6);
    }
  });
});

describe('buildTransition — global layout', () => {
  const a = version('term', 'en snabb buss kör genom staden varje kväll utan undantag');
  const b = version('term', 'en långsam buss kör genom staden varje natt utan undantag');

  it('marks all deletions together and collapses them together', () => {
    const t = buildTransition(a, b, 'global');
    const delWords = dels(t.def);
    expect(new Set(delWords.map((s) => s.ma)).size).toBe(1);
    expect(new Set(delWords.map((s) => s.ca)).size).toBe(1);
    // Typing happens strictly between mark and collapse.
    for (const ins of inss(t.def)) {
      expect(ins.a!).toBeGreaterThanOrEqual(delWords[0].ma! + delWords[0].ms! - 1e-6);
      expect(ins.a! + ins.span!).toBeLessThanOrEqual(delWords[0].ca! + 1e-6);
    }
  });
});

describe('buildTransition — misc', () => {
  it('identical versions yield a short transition with no thresholds', () => {
    const a = version('term', 'exakt samma text', ['X']);
    const t = buildTransition(a, version('term', 'exakt samma text', ['X']), 'sequential');
    expect(t.duration).toBeLessThan(2);
    expect(t.insBreakThresholds).toHaveLength(0);
    expect(t.delBreakThresholds).toHaveLength(0);
  });

  it('break thresholds are sorted (countPassed relies on early exit)', () => {
    const t = buildTransition(
      version('t', 'ett stycke.\n\nandra stycket.\n\ntredje stycket.'),
      version('t', 'ett stycke som växer.\n\nhelt nytt mellanstycke.\n\ntredje stycket kvar.'),
      'sequential'
    );
    const sorted = [...t.insBreakThresholds].sort((x, y) => x - y);
    expect(t.insBreakThresholds).toEqual(sorted);
    const sortedDel = [...t.delBreakThresholds].sort((x, y) => x - y);
    expect(t.delBreakThresholds).toEqual(sortedDel);
  });

  it('pill diff is unaffected by ordering mode', () => {
    const a = version('t', 'text', ['Behålls', 'Försvinner']);
    const b = version('t', 'text', ['Behålls', 'Tillkommer']);
    for (const order of ['sequential', 'global'] as const) {
      const t = buildTransition(a, b, order);
      expect(t.pills).toEqual([
        { label: 'Behålls', state: 'kept' },
        { label: 'Försvinner', state: 'removed' },
        { label: 'Tillkommer', state: 'added' }
      ]);
    }
  });
});

describe('buildTransition — formattingOnly', () => {
  it('flags markdown-only changes (prose untouched)', () => {
    const a = version('term', 'En hållplats är en plats där resenärer kliver på.');
    const b = version('term', 'En **hållplats** är en plats där resenärer kliver *på*.');
    const t = buildTransition(a, b, 'sequential');
    expect(t.insChars).toBe(0);
    expect(t.delChars).toBe(0);
    expect(t.formattingOnly).toBe(true);
  });

  it('stays false for real text changes and for identical versions', () => {
    const a = version('term', 'En text.');
    expect(buildTransition(a, version('term', 'En annan text.'), 'sequential').formattingOnly).toBe(
      false
    );
    expect(buildTransition(a, version('term', 'En text.'), 'sequential').formattingOnly).toBe(false);
  });
});
