import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Untranslated-text guard.
 *
 * Every user-facing string must go through the i18n layer (t() with a key, or
 * a content-by-language module). This test fails the build if it finds Swedish
 * diacritics (å ä ö) in *code* — i.e. a hardcoded string that bypasses i18n —
 * so a stray Swedish literal can never ship as untranslatable UI.
 *
 * It is a diacritic-based safety net, not a full Swedish detector: purely-ASCII
 * Swedish ("och", "med") slips through. That is an accepted trade-off for zero
 * false positives on English prose.
 *
 * A finding is legitimate in three cases, each with an explicit escape hatch:
 *   • content-by-language module — put `/* i18n-content *\/` in the file header;
 *     the whole file is skipped (it *is* the translation source).
 *   • one incidental line (sample data, a transliteration table) — append an
 *     `i18n-exempt: <reason>` comment to that line.
 *   • a whole authored block (e.g. an email drafted in Swedish on purpose) —
 *     bracket it with `i18n-exempt-start: <reason>` … `i18n-exempt-end`.
 * Comments (block, line and <!-- -->) are ignored, so Swedish developer prose
 * in comments is fine.
 */

const SRC = fileURLToPath(new URL('../../', import.meta.url)); // → src/

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else if (entry.isFile() && /\.(svelte|ts)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

/** Blank every comment (block, HTML and line) to spaces, preserving newlines so
 * line numbers survive. Swedish that survives this is Swedish in live code. */
function stripComments(text: string): string {
  const blank = (m: string) => m.replace(/[^\n]/g, ' ');
  const noBlocks = text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank);
  return noBlocks
    .split('\n')
    .map((line) => line.replace(/\/\/.*$/, ''))
    .join('\n');
}

function scan(rel: string, text: string): string[] {
  const original = text.split('\n');
  const code = stripComments(text).split('\n');
  const findings: string[] = [];
  let blockExempt = false;
  for (let i = 0; i < original.length; i++) {
    const line = original[i];
    if (line.includes('i18n-exempt-start')) blockExempt = true;
    const exempt = blockExempt || line.includes('i18n-exempt');
    if (!exempt && /[åäöÅÄÖ]/.test(code[i])) {
      findings.push(`${rel}:${i + 1}  ${line.trim().slice(0, 90)}`);
    }
    if (line.includes('i18n-exempt-end')) blockExempt = false;
  }
  return findings;
}

describe('i18n coverage guard', () => {
  it('has no Swedish diacritics in code outside content modules and pragmas', () => {
    const findings: string[] = [];
    for (const file of walk(SRC)) {
      const rel = relative(SRC, file).replaceAll('\\', '/');
      // Skip the translation dictionaries and this guard; skip tests.
      if (rel.startsWith('lib/i18n/')) continue;
      if (/\.(test|spec)\.ts$/.test(rel) || rel.endsWith('.d.ts')) continue;
      const text = readFileSync(file, 'utf8');
      // Content-by-language modules are the translation source, not UI code.
      if (text.slice(0, 300).includes('i18n-content')) continue;
      findings.push(...scan(rel, text));
    }
    if (findings.length > 0) {
      throw new Error(
        `Found ${findings.length} hardcoded Swedish string(s) that bypass i18n.\n` +
          `Route them through t() / a content module, or add an i18n-exempt pragma ` +
          `(see this file's header):\n\n` +
          findings.join('\n')
      );
    }
    expect(findings).toEqual([]);
  });
});
