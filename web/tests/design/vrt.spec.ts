import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

/**
 * Visuell regression (nivå 3): specimen-sidan är huvudytan — statisk,
 * datooberoende, täcker varje primitiv (per underlag-visuell-regression.md:
 * fixture-sidor frikopplar styling från innehåll). Sidytorna kompletterar
 * med chrome-regioner där data maskas.
 *
 * Baselines: plattformssuffixade; uppdatera med --update-snapshots och
 * granska diffen som ett DESIGNBESLUT (aldrig auto-accept — research-final).
 */

const MANUAL = 'file://' + fileURLToPath(new URL('../../design-system.html', import.meta.url));
const THEMES = ['light', 'dark', 'contrast'] as const;

for (const theme of THEMES) {
  test(`manualen renderar stabilt [${theme}]`, async ({ page }) => {
    await page.goto(MANUAL);
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    await page.waitForTimeout(250);
    await expect(page).toHaveScreenshot(`manual-${theme}.png`, { fullPage: true });
  });
}

test('sidhuvud + hero (chrome, data maskat)', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page).toHaveScreenshot('home-chrome.png', {
    clip: { x: 0, y: 0, width: 1440, height: 620 },
    mask: [page.locator('.results, [class*="results"]')],
  });
});

test('collections-sidans huvud (data maskat)', async ({ page }) => {
  await page.goto('/collections', { waitUntil: 'networkidle' });
  await expect(page).toHaveScreenshot('collections-chrome.png', {
    clip: { x: 0, y: 0, width: 1440, height: 380 },
    mask: [page.locator('.card-grid')],
  });
});
