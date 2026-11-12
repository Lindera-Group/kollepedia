import { describe, it, expect } from 'vitest';
// Plain-node guard module (ts-nocheck'd), imported untyped by design.
import { runGuard } from '../../scripts/design-guard.mjs';

/**
 * Design-system guard (2026-07-12) — the mechanical twin of the i18n guard.
 *
 * ZERO TOLERANCE: components may not hardcode CSS. Everything visual comes
 * from the primitives/tokens in src/app.css, every primitive is demonstrated
 * in design-system.html, and every token exists in all three themes. The
 * rules and their rationale live in scripts/design-guard.mjs; the visual
 * spec in web/design-system.html; checklists in the ui-guardrails
 * skill.
 *
 * The same guard runs in the repo pre-commit hook (.githooks/pre-commit);
 * this test makes CI enforce it even past a --no-verify commit.
 *
 * Escape hatch (rare, must carry a reason):
 *   some-css: value; /* design-guard-exempt: <reason> *\/
 */

type Finding = { file: string; line: number; rule: string; detail: string };

describe('design system guard', () => {
  it('has no hardcoded CSS, no primitive re-implementations, manual and themes in sync', () => {
    const findings = runGuard() as Finding[];
    if (findings.length > 0) {
      const lines = findings.map((f) => `${f.file}:${f.line}  [${f.rule}]  ${f.detail}`);
      throw new Error(
        `Found ${findings.length} design-system violation(s). ` +
          `Use the app.css primitives/tokens (see web/design-system.html):\n\n` +
          lines.join('\n')
      );
    }
    expect(findings).toEqual([]);
  });
});
