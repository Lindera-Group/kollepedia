import { test, expect, type Page } from '@playwright/test';

/**
 * Rytmkontraktet — tvärsides-invarianter som grep aldrig kan se (nivå 3).
 * Få och semantiska, per research-final.md: varje assertion vaktar ett
 * designbeslut, inte en implementationsdetalj.
 *
 * Prejudikat: 5.5px-buggen (2026-07-13) — h1→ingress-gapet varierade med
 * actions-slottens innehåll via flexbox-baseline. Fixad i .page-head-row
 * (align-items: center); invarianten här ser till att den aldrig kommer åter.
 */

/** Publika sidor som öppnar med PageHeader + intro. */
const PAGES = ['/collections', '/authors', '/categories', '/orgs', '/most-watched'];

async function metrics(page: Page, path: string) {
  await page.goto(path, { waitUntil: 'networkidle' });
  return page.evaluate(() => {
    const h1 = document.querySelector('.page-head h1');
    const intro = document.querySelector('.page-head-intro');
    const container = document.querySelector('main .container');
    const root = getComputedStyle(document.documentElement);
    return {
      gap: h1 && intro
        ? intro.getBoundingClientRect().top - h1.getBoundingClientRect().bottom
        : null,
      h1Size: h1 ? getComputedStyle(h1).fontSize : null,
      containerWidth: container ? container.getBoundingClientRect().width : null,
      text2xl: root.getPropertyValue('--text-2xl').trim(),
    };
  });
}

test.describe('rytmkontrakt', () => {
  test('h1→ingress-gapet är identiskt på alla PageHeader-sidor', async ({ page }) => {
    const gaps: Record<string, number> = {};
    for (const path of PAGES) {
      const m = await metrics(page, path);
      expect(m.gap, `${path} saknar page-head h1+intro`).not.toBeNull();
      gaps[path] = m.gap!;
    }
    const values = Object.values(gaps);
    const spread = Math.max(...values) - Math.min(...values);
    expect(spread, `gapen divergerar: ${JSON.stringify(gaps)}`).toBeLessThanOrEqual(0.6);
  });

  test('h1 följer den globala skalan (--text-2xl) på alla sidor', async ({ page }) => {
    for (const path of PAGES) {
      const m = await metrics(page, path);
      // 2.2rem = 35.2px vid 16px-rot — men assertera token-relativt, inte px.
      const expected = parseFloat(m.text2xl) * 16;
      expect(parseFloat(m.h1Size!), `${path}: h1 ≠ --text-2xl`).toBeCloseTo(expected, 1);
    }
  });

  test('sidskalet håller standardbredden (1100px) överallt', async ({ page }) => {
    for (const path of [...PAGES, '/compare']) {
      const m = await metrics(page, path);
      expect(m.containerWidth, `${path}: containerbredd`).toBeLessThanOrEqual(1100.5);
    }
  });

  test('wordmarken bär brand-token och logotypvikten', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    const wm = await page.evaluate(() => {
      const el = document.querySelector('.wordmark');
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { weight: cs.fontWeight, size: parseFloat(cs.fontSize) };
    });
    expect(wm).not.toBeNull();
    expect(wm!.weight).toBe('600');
    // clamp(1.7rem, …, 2.35rem) → inom spannet, aldrig utanför
    expect(wm!.size).toBeGreaterThanOrEqual(1.7 * 16 - 0.5);
    expect(wm!.size).toBeLessThanOrEqual(2.35 * 16 + 0.5);
  });
});
