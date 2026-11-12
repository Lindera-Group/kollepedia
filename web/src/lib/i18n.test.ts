import { afterEach, describe, expect, it } from 'vitest';
import { en } from './i18n/en';
import { sv } from './i18n/sv';
import { formatDate, formatNumber, i18n, languageLabel, setLang, statusLabel, t } from './i18n.svelte';

// Every test leaves the store back on the Swedish default.
afterEach(() => setLang('sv'));

describe('dictionary parity (regression guard from the prototype)', () => {
  it('sv and en expose identical key sets', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(sv).sort());
  });

  it('has no empty translations in either language', () => {
    for (const [key, value] of Object.entries(sv)) {
      expect(value.length, `sv[${key}]`).toBeGreaterThan(0);
    }
    for (const [key, value] of Object.entries(en)) {
      expect(value.length, `en[${key}]`).toBeGreaterThan(0);
    }
  });

  it('keeps {param} placeholders consistent between languages', () => {
    const params = (text: string): string[] => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(sv) as (keyof typeof sv)[]) {
      expect(params(en[key]), `placeholders for ${key}`).toEqual(params(sv[key]));
    }
  });
});

describe('t()', () => {
  it('returns Swedish by default', () => {
    expect(i18n.lang).toBe('sv');
    expect(t('common.save')).toBe('Spara');
  });

  it('switches to English via setLang', () => {
    setLang('en');
    expect(i18n.lang).toBe('en');
    expect(t('common.save')).toBe('Save');
  });

  it('interpolates {param} tokens in both languages', () => {
    expect(t('tm.version_x_of_y', { x: 2, y: 7 })).toBe('Version 2 av 7');
    setLang('en');
    expect(t('tm.version_x_of_y', { x: 2, y: 7 })).toBe('Version 2 of 7');
  });

  it('interpolates multiple parameters', () => {
    expect(t('coll.pager', { from: 1, to: 30, total: 90 })).toBe('1–30 av 90');
  });
});

describe('formatDate', () => {
  // No trailing Z: parsed as local time, so the calendar day is stable in any TZ.
  const iso = '2026-07-04T12:00:00';

  it('uses the sv-SE locale by default', () => {
    expect(formatDate(iso)).toBe('4 juli 2026');
  });

  it('uses the en-GB locale when the UI language is English', () => {
    setLang('en');
    expect(formatDate(iso)).toBe('4 July 2026');
  });
});

describe('formatNumber', () => {
  it('follows the UI language locale', () => {
    // sv-SE groups thousands with a narrow no-break/space; en-GB with a comma.
    expect(formatNumber(1234).at(-3)).not.toBe(',');
    setLang('en');
    expect(formatNumber(1234)).toBe('1,234');
  });
});

describe('statusLabel / languageLabel', () => {
  it('translates known values and passes unknown values through', () => {
    expect(statusLabel('endorsed')).toBe('fastställd');
    expect(languageLabel('sv')).toBe('svenska');
    expect(statusLabel('mystery')).toBe('mystery');
    expect(languageLabel('fi')).toBe('fi');
    setLang('en');
    expect(statusLabel('endorsed')).toBe('endorsed');
    expect(languageLabel('sv')).toBe('Swedish');
  });
});
