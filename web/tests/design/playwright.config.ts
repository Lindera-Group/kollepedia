import { defineConfig, devices } from '@playwright/test';

/**
 * Nivå 3-harnessen (designkontraktet, research steg 2): rytmkontrakt,
 * deterministisk a11y-grind och visuell regression.
 *
 * Körs mot den LOKALA stacken (dev-server 5181 + backend 8088):
 *   npm run test:design            # kontrakt + axe
 *   npm run test:design:vrt        # även skärmbildsjämförelser
 *   npx playwright test --config tests/design/playwright.config.ts --update-snapshots
 *
 * Skärmbildsbaselines är plattformssuffixade (…-darwin.png lokalt). CI på
 * linux genererar sina egna i Playwright-Dockerimagen — generera ALDRIG
 * linux-baselines från macOS (ARM/x64-fällan, se research-final.md).
 */
export default defineConfig({
  testDir: '.',
  outputDir: '/tmp/claude-501/ng-design-results',
  fullyParallel: true,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
      caret: 'hide',
    },
  },
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://localhost:5181',
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5181',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
