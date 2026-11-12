import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sv } from './sv';
import { en } from './en';
import { helpTopics } from '$lib/help/topics';
import { manual } from '../../routes/manual/content';
import { pricingContent } from '../../routes/pricing/content';
import { aboutContent } from '../../routes/about/content';
import { shareContent } from '../../routes/collections/share/content';

/**
 * Typography guard: the dash.
 *
 * Swedish never uses the em dash (—); the sentence dash is the en dash (–,
 * tankstreck). English keeps the em dash, and nothing longer than an em dash
 * (horizontal bar, two-/three-em dashes, doubled dashes) is allowed in either
 * language. Language-neutral markup (page titles, separators, empty cells)
 * must take its dash from t('typo.dash') instead of a literal, so the right
 * glyph follows the UI language.
 *
 * Three checks:
 *   1. the Swedish dictionaries and the Swedish half of every
 *      content-by-language module contain no em dash;
 *   2. no dictionary or content module contains a dash longer than an em dash;
 *   3. live code (comments stripped) contains no em dash literal outside the
 *      English dictionaries and the content-by-language modules.
 */

const EM = '—';
const LONGER = /[―⸺⸻]|——|––/;

const SRC = fileURLToPath(new URL('../../', import.meta.url)); // → src/

function strings(value: unknown, path: string, out: [string, string][]): void {
  if (typeof value === 'string') {
    out.push([path, value]);
  } else if (Array.isArray(value)) {
    value.forEach((item, i) => strings(item, `${path}[${i}]`, out));
  } else if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) strings(item, `${path}.${key}`, out);
  }
}

const contentModules: Record<string, Record<'sv' | 'en', unknown>> = {
  manual,
  pricingContent,
  aboutContent,
  shareContent,
  helpTopics
};

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

/** Blank every comment (block, HTML and line) to spaces, preserving newlines. */
function stripComments(text: string): string {
  const blank = (m: string) => m.replace(/[^\n]/g, ' ');
  const noBlocks = text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank);
  return noBlocks
    .split('\n')
    .map((line) => line.replace(/\/\/.*$/, ''))
    .join('\n');
}

describe('typography guard: dashes', () => {
  it('uses the en dash in Swedish UI copy, never the em dash', () => {
    const offenders = Object.entries(sv)
      .filter(([, value]) => value.includes(EM))
      .map(([key]) => key);
    expect(offenders, 'sv dictionary keys with an em dash').toEqual([]);
  });

  it('uses the en dash in the Swedish half of every content module', () => {
    const offenders: string[] = [];
    for (const [name, mod] of Object.entries(contentModules)) {
      const found: [string, string][] = [];
      strings(mod.sv, `${name}.sv`, found);
      for (const [path, value] of found) if (value.includes(EM)) offenders.push(path);
    }
    expect(offenders, 'Swedish content strings with an em dash').toEqual([]);
  });

  it('never uses a dash longer than the em dash, in either language', () => {
    const offenders: string[] = [];
    for (const [key, value] of Object.entries(en)) if (LONGER.test(value)) offenders.push(`en.${key}`);
    for (const [key, value] of Object.entries(sv)) if (LONGER.test(value)) offenders.push(`sv.${key}`);
    for (const [name, mod] of Object.entries(contentModules)) {
      const found: [string, string][] = [];
      strings(mod, name, found);
      for (const [path, value] of found) if (LONGER.test(value)) offenders.push(path);
    }
    expect(offenders, 'strings with a dash longer than the em dash').toEqual([]);
  });

  it('takes the dash in language-neutral markup from t("typo.dash"), not a literal', () => {
    expect(sv['typo.dash']).toBe('–');
    expect(en['typo.dash']).toBe(EM);
    const findings: string[] = [];
    for (const file of walk(SRC)) {
      const rel = relative(SRC, file);
      if (/\.test\.ts$/.test(rel)) continue;
      if (/^lib\/i18n\/en(-[a-z]+)?\.ts$/.test(rel)) continue;
      const text = readFileSync(file, 'utf8');
      if (text.includes('/* i18n-content */')) continue;
      const code = stripComments(text).split('\n');
      code.forEach((line, i) => {
        if (line.includes(EM)) findings.push(`${rel}:${i + 1}: ${line.trim()}`);
      });
    }
    expect(findings, 'em dash literals in live code').toEqual([]);
  });
});
