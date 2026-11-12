import { describe, expect, it } from 'vitest';
import { charCount, diffText, diffTokens, tokenize } from './diff';

function joined(text: string): string {
  return tokenize(text)
    .map((t) => t.text)
    .join('');
}

describe('tokenize', () => {
  it('round-trips text exactly', () => {
    const text = 'En hållplats är  en plats.\n\nDär stannar fordon,\noch resenärer kliver av.';
    expect(joined(text)).toBe(text);
  });

  it('attaches trailing spaces to words and isolates newline runs', () => {
    const tokens = tokenize('ett två\n\ntre');
    expect(tokens.map((t) => t.kind)).toEqual(['word', 'word', 'break', 'word']);
    expect(tokens[0].text).toBe('ett ');
  });
});

describe('diffTokens', () => {
  it('marks identical texts as all-equal', () => {
    const ops = diffText('samma text här', 'samma text här');
    expect(ops).toHaveLength(1);
    expect(ops[0].type).toBe('eq');
  });

  it('detects a single word replacement as del+ins', () => {
    const ops = diffText('bussen stannar vid hållplatsen', 'bussen stannar vid stationen');
    const types = ops.map((o) => o.type);
    expect(types).toEqual(['eq', 'del', 'ins']);
    expect(ops[1].tokens[0].text.trim()).toBe('hållplatsen');
    expect(ops[2].tokens[0].text.trim()).toBe('stationen');
  });

  it('reconstructs A from eq+del and B from eq+ins', () => {
    const a = 'spårvagnen går på räls genom staden';
    const b = 'spårvagnen kör på räls genom hela innerstaden';
    const ops = diffText(a, b);
    const bRebuilt = ops
      .filter((o) => o.type !== 'del')
      .flatMap((o) => o.tokens)
      .map((t) => t.text)
      .join('');
    expect(bRebuilt).toBe(b);
    // A rebuilt modulo trailing whitespace (eq tokens carry B-side spacing).
    const aRebuilt = ops
      .filter((o) => o.type !== 'ins')
      .flatMap((o) => o.tokens)
      .map((t) => t.text.trimEnd())
      .join(' ');
    expect(aRebuilt.replace(/\s+/g, ' ')).toBe(a.replace(/\s+/g, ' '));
  });

  it('handles empty sides', () => {
    expect(diffText('', 'ny text')[0].type).toBe('ins');
    expect(diffText('gammal text', '')[0].type).toBe('del');
    expect(diffText('', '')).toHaveLength(0);
  });

  it('handles paragraph insertion (break tokens)', () => {
    const ops = diffText('första stycket.', 'första stycket.\n\nandra stycket.');
    const ins = ops.filter((o) => o.type === 'ins').flatMap((o) => o.tokens);
    expect(ins.some((t) => t.kind === 'break')).toBe(true);
    expect(charCount(ops, 'ins')).toBeGreaterThan(0);
  });

  it('survives a large rewrite without losing tokens', () => {
    const a = 'Trafikutbudet omfattar samtliga linjer som körs under en trafikdag.';
    const b = 'Med trafikutbud avses den samlade mängden trafik som erbjuds resenärerna, uttryckt i linjer, turer och tidtabeller under en given period.';
    const ops = diffTokens(tokenize(a), tokenize(b));
    const bTokens = ops.filter((o) => o.type !== 'del').flatMap((o) => o.tokens);
    expect(bTokens.map((t) => t.text).join('')).toBe(b);
  });
});
