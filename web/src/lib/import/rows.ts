/** Pure helpers for the AI-extraction preview → import-rows flow. */

import type { ImportRow } from '$lib/api';

/** Trim all values, drop empty fields, and drop rows that carry nothing.
 * The server validates for real — this only keeps the payload clean. */
export function cleanRows(rows: ImportRow[]): ImportRow[] {
  const cleaned: ImportRow[] = [];
  for (const row of rows) {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(row)) {
      const trimmed = typeof value === 'string' ? value.trim() : '';
      if (trimmed) out[key] = trimmed;
    }
    if (Object.keys(out).length > 0) cleaned.push(out as unknown as ImportRow);
  }
  return cleaned;
}

/** True when a dry run is clean enough to enable the real import:
 * at least one row would be created. */
export function canImport(result: { created: number } | null): boolean {
  return !!result && result.created > 0;
}
