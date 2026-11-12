import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import allowlist from './axe-allowlist.json' with { type: 'json' };

/**
 * Deterministisk tillgänglighetsgrind (nivå 3): axe-core (WCAG 2.x A/AA)
 * per sida × tema. Kontrast är beräkningsbar — tre teman med tematvång men
 * utan kontrastkontroll vore ett hål (Bengts review-punkt 9).
 *
 * Ratchet-regim: KÄNDA fynd ligger i axe-allowlist.json med motivering och
 * väntar på [M]-beslut (palettändringar är designbeslut, inte nattarbete).
 * NYA fynd failar direkt. Tomma allowlist-poster tas bort vid regelrevision.
 */

const PAGES = ['/', '/collections', '/authors', '/categories', '/orgs', '/compare'];
const THEMES = ['light', 'dark', 'contrast'] as const;

type AllowKey = string; // "<tema> <sida> <regel-id>"
const allowed = new Set<AllowKey>(allowlist.allowed.map((a: { key: string }) => a.key));

for (const theme of THEMES) {
  for (const path of PAGES) {
    test(`axe: ${path} [${theme}]`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'networkidle' });
      await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
      await page.waitForTimeout(150);
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      const fresh = results.violations.filter(
        (v) => !allowed.has(`${theme} ${path} ${v.id}`)
      );
      expect(
        fresh.map((v) => ({
          key: `${theme} ${path} ${v.id}`,
          impact: v.impact,
          help: v.help,
          nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
        }))
      ).toEqual([]);
    });
  }
}
