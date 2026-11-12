import { describe, expect, it } from 'vitest';
import { canImport, cleanRows } from './rows';
import type { ImportRow } from '$lib/api';

describe('cleanRows', () => {
  it('trims values and drops empty fields', () => {
    const rows = [
      { canonical_form: '  hållplats ', definition: 'En plats.', tags: '  ' }
    ] as ImportRow[];
    expect(cleanRows(rows)).toEqual([{ canonical_form: 'hållplats', definition: 'En plats.' }]);
  });

  it('drops rows that carry nothing', () => {
    const rows = [
      { canonical_form: '', definition: ' ' },
      { canonical_form: 'zon', definition: 'Ett område.' }
    ] as ImportRow[];
    expect(cleanRows(rows)).toEqual([{ canonical_form: 'zon', definition: 'Ett område.' }]);
  });

  it('keeps partially filled rows so the server can report them', () => {
    const rows = [{ canonical_form: 'zon', definition: '' }] as ImportRow[];
    expect(cleanRows(rows)).toEqual([{ canonical_form: 'zon' }]);
  });
});

describe('canImport', () => {
  it('requires a dry run with at least one creatable row', () => {
    expect(canImport(null)).toBe(false);
    expect(canImport({ created: 0 })).toBe(false);
    expect(canImport({ created: 3 })).toBe(true);
  });
});
