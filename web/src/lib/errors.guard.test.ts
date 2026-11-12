import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Raw-API-error guard (plan NG_ATTRIBUTION_OCH_FELHANTERING, paket E3).
 *
 * `ApiError.detail` is English log text and must never be rendered to the
 * user — all user-facing error text goes through errorMessage() in
 * $lib/errors, which maps the machine-readable `code` to a localized
 * apierr.* key with localized fallbacks. This test fails the build when it
 * finds the old idiom creeping back in:
 *
 *   • `instanceof ApiError … .detail` on one line (the classic
 *     `e instanceof ApiError ? e.detail : String(e)` pattern), or
 *   • a bare `e.detail` / `err.detail` member access in a .svelte file.
 *
 * `event.detail` (DOM CustomEvent) is allowed. A legitimate exception (e.g.
 * debug logging) gets an `apierr-exempt: <reason>` comment on the line.
 */

const SRC = fileURLToPath(new URL('../', import.meta.url)); // → src/

const ALLOWED = new Set(['lib/api.ts', 'lib/errors.ts']);

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

const IDIOM = /instanceof\s+ApiError[^\n;]*\.detail\b/;
const BARE = /\b(?:e|err|error)\.detail\b/;

function scan(rel: string, text: string): string[] {
  const findings: string[] = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes('apierr-exempt')) continue;
    if (IDIOM.test(line) || BARE.test(line)) {
      findings.push(`${rel}:${i + 1}  ${line.trim().slice(0, 90)}`);
    }
  }
  return findings;
}

describe('raw API error guard', () => {
  it('renders no raw ApiError.detail outside $lib/api and $lib/errors', () => {
    const findings: string[] = [];
    for (const file of walk(SRC)) {
      const rel = relative(SRC, file).replaceAll('\\', '/');
      if (ALLOWED.has(rel)) continue;
      if (/\.(test|spec)\.ts$/.test(rel) || rel.endsWith('.d.ts')) continue;
      findings.push(...scan(rel, readFileSync(file, 'utf8')));
    }
    if (findings.length > 0) {
      throw new Error(
        `Found ${findings.length} raw ApiError.detail usage(s). Route the text ` +
          `through errorMessage() from $lib/errors, or add an apierr-exempt ` +
          `pragma with a reason:\n\n` +
          findings.join('\n')
      );
    }
    expect(findings).toEqual([]);
  });
});
