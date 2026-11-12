#!/usr/bin/env node
// @ts-nocheck — plain-node tool, deliberately untyped (run: node scripts/design-guard.mjs)
/**
 * Design guard — the mechanical gate for the NG design system.
 *
 * ZERO TOLERANCE: hardcoded CSS values are not allowed in components.
 * Everything visual must come from the primitives in src/app.css, and every
 * primitive must be demonstrated in design-system.html. This script is the
 * enforcement — not memory, not discipline (decision 2026-07-12).
 *
 * Scope: web/src/**\/*.svelte (style blocks + style attributes) and any
 * .css file that is not app.css. app.css itself IS the primitive layer and is
 * only checked for theme parity and manual coverage.
 *
 * Rules
 *   undefined-token     var(--x) must be assigned somewhere: app.css, a style
 *                       block, a style attribute, style:--x={}, setProperty
 *   hex-color           no #hex literals in component styles
 *   raw-color-fn        no rgb()/rgba()/hsl()/oklch() literals (color-mix over
 *                       tokens is fine — literals inside it trip other rules)
 *   font-size-literal   font-size must be var(--text-*) (em/%/inherit/0 ok)
 *   font-family-literal font-family must be var(--font-*) (or inherit)
 *   radius-literal      border-radius must be var(--radius-*) (or 0)
 *   spacing-literal     padding/margin/gap must be var(--space-*) (0/auto/em/% ok)
 *   transition-all      never `transition: all`
 *   banned-selector     no local .badge/.sr-only/.visually-hidden/.filter-btn/
 *                       v1 button names; no redefinition of global primitives
 *   emoji-icon          no emoji/ad-hoc glyph icons in .svelte — use $lib/icons
 *                       (Icon.svelte); typographic arrows/dashes are exempt
 *   manual-coverage     every class defined in app.css appears in
 *                       design-system.html (the manual may never drift)
 *   theme-parity        every token exists in all three themes
 *
 * Escape hatch (rare, must carry a reason — mirrors the i18n guard):
 *   some-css: value; /* design-guard-exempt: <reason> *\/
 *
 * Run:  node scripts/design-guard.mjs        (from web)
 * Test: src/lib/design.guard.test.ts wraps runGuard() so CI enforces it too.
 */

import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = dirname(fileURLToPath(new URL(import.meta.url))) // → scripts/
  .replace(/scripts$/, '');
const SRC = join(WEB, 'src');
const APP_CSS = join(SRC, 'app.css');
const MANUAL = join(WEB, 'design-system.html');

// ── file walking ────────────────────────────────────────────────────────────

function walk(dir, exts = /\.(svelte|css)$/) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full, exts));
    else if (exts.test(entry.name)) out.push(full);
  }
  return out;
}

/** Blank a span to spaces, preserving newlines so line numbers survive. */
const blank = (m) => m.replace(/[^\n]/g, ' ');

function stripCssComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, blank);
}

/** Extract <style> blocks with their global line offsets. */
function styleBlocks(svelteText) {
  const blocks = [];
  const re = /<style[^>]*>([\s\S]*?)<\/style>/g;
  let m;
  while ((m = re.exec(svelteText)) !== null) {
    const before = svelteText.slice(0, m.index + m[0].indexOf('>') + 1);
    blocks.push({ css: m[1], lineOffset: before.split('\n').length - 1 });
  }
  return blocks;
}

// ── token collection ────────────────────────────────────────────────────────

function collectAssignedTokens(files, appCssText) {
  const assigned = new Set();
  const collect = (text) => {
    for (const m of text.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)) assigned.add(m[1]);
    for (const m of text.matchAll(/style:(--[a-zA-Z0-9-]+)/g)) assigned.add(m[1]);
    for (const m of text.matchAll(/setProperty\(\s*['"`](--[a-zA-Z0-9-]+)/g)) assigned.add(m[1]);
  };
  collect(appCssText);
  for (const f of files) collect(readFileSync(f, 'utf8'));
  // Runtime-set tokens (setProperty in .ts modules, e.g. the Time Machine's
  // playback engine) count as assignments too.
  for (const f of walk(SRC, /\.ts$/)) collect(readFileSync(f, 'utf8'));
  return assigned;
}

// ── declaration-level checks (one line of CSS at a time) ────────────────────

// Pictographic emoji + ad-hoc icon glyphs that must instead come from
// $lib/icons. Ranges: Misc Symbols & Dingbats (2600–27BF: ★ ✓ ✗ ❄ ⚲ ☀ …),
// emoji blocks (1F000–1FAFF: 🔒 🔔 💬 …), plus explicit ⊘ ⧗ ⏳. Typographic
// arrows (2190–21FF) and punctuation are deliberately excluded — not icons.
const EMOJI_ICON =
  /[☀-➿⊘⧗⏳\u{1F000}-\u{1FAFF}⬀-⯿️]/u;

const SPACING_PROPS = /(?:^|[^a-z-])(padding|margin|gap|row-gap|column-gap|padding-top|padding-right|padding-bottom|padding-left|margin-top|margin-right|margin-bottom|margin-left)\s*:\s*([^;{}]+)/g;

/** Replace every calc(...) group that composes a token with '0' — balanced-
 * paren walk, since calc nests var() groups regex can't match reliably. */
function blankTokenCalcs(value) {
  let out = '';
  for (let i = 0; i < value.length; i++) {
    if (value.startsWith('calc(', i)) {
      let depth = 0, j = i + 4;
      do {
        if (value[j] === '(') depth++;
        else if (value[j] === ')') depth--;
        j++;
      } while (depth > 0 && j < value.length);
      const group = value.slice(i, j);
      out += group.includes('var(--') ? '0' : group;
      i = j - 1;
    } else {
      out += value[i];
    }
  }
  return out;
}

function checkCssLine(line) {
  const findings = []; // [rule, detail]

  for (const m of line.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
    findings.push(['hex-color', m[0]]);
  }
  for (const m of line.matchAll(/\b(rgba?|hsla?|oklch)\(/g)) {
    findings.push(['raw-color-fn', m[0]]);
  }

  const fontSize = line.match(/font-size\s*:\s*([^;{}]+)/);
  if (fontSize && /\d(px|rem|pt)\b/.test(fontSize[1]) && !/var\(--text-/.test(fontSize[1])) {
    findings.push(['font-size-literal', fontSize[1].trim()]);
  }

  const fontFamily = line.match(/font-family\s*:\s*([^;{}]+)/);
  if (fontFamily && !/var\(--font-|^\s*inherit\s*$/.test(fontFamily[1])) {
    findings.push(['font-family-literal', fontFamily[1].trim()]);
  }

  const radius = line.match(/border-radius\s*:\s*([^;{}]+)/);
  if (radius) {
    const parts = radius[1].trim().split(/\s+/);
    for (const p of parts) {
      if (p.startsWith('var(--radius-') || p === '0' || p === 'inherit') continue;
      findings.push(['radius-literal', radius[1].trim()]);
      break;
    }
  }

  for (const m of line.matchAll(SPACING_PROPS)) {
    // calc() that composes tokens is fine (incl. small px compensations
    // inside it); blank those groups before checking the remaining parts.
    const value = blankTokenCalcs(m[2]);
    const parts = value.trim().split(/\s+/);
    for (const p of parts) {
      const ok =
        p.startsWith('var(--space-') ||
        p === '0' ||
        p === 'auto' ||
        /^-?[\d.]+(em|%)$/.test(p) ||
        /^-?[12]px$/.test(p); // hairline compensation/gaps only
      if (!ok) {
        findings.push(['spacing-literal', `${m[1]}: ${m[2].trim()}`]);
        break;
      }
    }
  }

  if (/transition\s*:[^;{}]*\ball\b/.test(line)) {
    findings.push(['transition-all', 'transition: all']);
  }

  return findings;
}

// ── selector-level checks ───────────────────────────────────────────────────

/** Names that may never be (re)defined in a component style block. */
const BANNED_NAMES = new Set([
  // duplicated-primitive smells
  'badge', 'sr-only', 'visually-hidden', 'filter-btn',
  // v1 muscle memory
  'save-btn', 'cancel-btn', 'delete-btn',
]);

/** Global primitives — overriding them locally is drift by definition. */
const GLOBAL_PRIMITIVES = new Set([
  'btn', 'btn-primary', 'btn-quiet', 'btn-danger', 'icon-btn',
  'pill', 'count-badge', 'filter-chip', 'cat-pill', 'tag-pill',
  'card', 'card-grid', 'subview', 'subview-h', 'subview-hint', 'subview-actions',
  'page-head', 'page-head-row', 'page-head-intro', 'page-head-actions',
  'guard', 'breadcrumb', 'container', 'input', 'field-label',
]);

/** Form controls must use the .input primitive — a bare element selector in a
 * component is how the 41 copy-pasted input recipes happened. Only fires when
 * the block actually re-implements the recipe (border/padding/background);
 * checkbox sizing, file-input hiding etc. pass. */
const RAW_ELEMENT_SUBJECTS = /^(input|textarea|select)(\[[^\]]*\])?(::?[a-z-]+(\([^)]*\))?)*$/;
const CHECKBOXY = /\[type=['"]?(checkbox|radio|file|range)/;
const RECIPE_MARKERS = /(?:^|[^-a-z])(border|border-color|padding|background)\s*:/;

function blockBody(lines, startIdx) {
  // Flat CSS in Svelte components: collect from the "{" to the closing "}".
  const body = [];
  for (let i = startIdx; i < lines.length; i++) {
    body.push(lines[i]);
    if (lines[i].includes('}')) break;
  }
  return body.join('\n');
}

function checkSelectors(css, lineOffset, rel, findings, exemptLines) {
  // Match "selector {" — good enough for the flat CSS Svelte components use.
  const lines = css.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^\s*([^{}@/][^{}]*)\{/);
    if (!m) continue;
    const lineNo = lineOffset + i + 1;
    if (exemptLines.has(lineNo)) continue;
    for (const sel of m[1].split(',')) {
      // Every class mentioned anywhere in the selector is checked: styling
      // ".row .pill" locally is still overriding the global pill.
      for (const cls of sel.matchAll(/\.([a-zA-Z][a-zA-Z0-9-]*)/g)) {
        const name = cls[1];
        if (BANNED_NAMES.has(name)) {
          findings.push({ file: rel, line: lineNo, rule: 'banned-selector', detail: `.${name} — use the app.css primitive instead` });
        } else if (GLOBAL_PRIMITIVES.has(name)) {
          findings.push({ file: rel, line: lineNo, rule: 'banned-selector', detail: `.${name} is a global primitive — never restyle it locally` });
        }
      }
      // Bare form-control element subjects re-implementing the input recipe.
      const subject = sel.trim().split(/\s+|>|\+|~/).pop() ?? '';
      if (RAW_ELEMENT_SUBJECTS.test(subject) && !CHECKBOXY.test(subject)) {
        if (RECIPE_MARKERS.test(blockBody(lines, i))) {
          findings.push({ file: rel, line: lineNo, rule: 'raw-element-selector', detail: `"${sel.trim()}" — use the .input primitive, don't re-style form controls` });
        }
      }
    }
  }
}

// ── Level 2: page structure & IA policy (2026-07-13) ────────────────────────
// The superordinate rules — deliberate, enumerated, never emergent:
//   · Every static page opens with <PageHeader> (index/tool/admin pattern).
//     Detail pages (dynamic [param] routes) use the content-header pattern
//     instead: breadcrumb + their own content h1.
//   · Breadcrumbs mark IA descent and nothing else: REQUIRED on detail pages
//     and the enumerated static children of a hub/flow; FORBIDDEN on
//     top-level pages. A back-link styled as a breadcrumb is a breadcrumb.
//   · Prose is serif. `.ui` (sans) belongs to chrome only — never on
//     intro/tagline/lead paragraphs (the v1 rule, re-adopted 2026-07-13).
// File-level escape hatch: `design-guard-exempt-structure: <reason>`.

const HERO_PAGES = new Set(['']); // home — the sanctioned hero replaces PageHeader
const AUTH_PAGES = new Set(['activate', 'reset', 'verify-email']); // auth-card pattern
const DOC_PAGES = new Set(['about', 'manual', 'pricing']); // document pages: own h1
const STATIC_CHILDREN = new Set([ // static routes that ARE children of a hub/flow
  'new-collection', 'new-concept', 'most-watched', 'collections/share',
  'admin/events', 'admin/outbox', 'admin/outreach', 'admin/taxonomies', 'admin/users',
]);

const PROSE_UI =
  /class="(?=[^"]*\b(?:page-head-intro|tagline|intro|lead)\b)(?=[^"]*\bui\b)[^"]*"/;

function checkPageStructure(files, findings) {
  for (const file of files) {
    if (!file.endsWith('+page.svelte')) continue;
    const rel = relative(WEB, file).replaceAll('\\', '/');
    const route = rel.replace('src/routes/', '').replace(/\/?\+page\.svelte$/, '');
    const text = readFileSync(file, 'utf8');
    if (text.includes('design-guard-exempt-structure')) continue;

    const isDynamic = route.includes('[');
    const hasPageHeader = /<PageHeader\b/.test(text);
    const hasBreadcrumb = /breadcrumb/.test(text);
    const exemptFromHeader = HERO_PAGES.has(route) || AUTH_PAGES.has(route) || DOC_PAGES.has(route);

    if (!isDynamic && !exemptFromHeader && !hasPageHeader) {
      findings.push({ file: rel, line: 1, rule: 'page-structure', detail: `static page "/${route}" must open with <PageHeader> (or carry design-guard-exempt-structure with a reason)` });
    }
    const breadcrumbRequired = isDynamic || STATIC_CHILDREN.has(route);
    if (breadcrumbRequired && !hasBreadcrumb) {
      findings.push({ file: rel, line: 1, rule: 'breadcrumb-policy', detail: `"/${route}" is a detail/child page — it must render a .breadcrumb` });
    } else if (!breadcrumbRequired && hasBreadcrumb) {
      findings.push({ file: rel, line: 1, rule: 'breadcrumb-policy', detail: `"/${route}" is a top-level page — breadcrumbs mark IA descent and are forbidden here` });
    }
  }
}

// ── app.css ↔ manual + theme parity ─────────────────────────────────────────

function appCssClasses(appCssText) {
  const css = stripCssComments(appCssText);
  const classes = new Set();
  for (const m of css.matchAll(/^\s*([^{}@/][^{}]*)\{/gm)) {
    for (const cls of m[1].matchAll(/\.([a-zA-Z][a-zA-Z0-9-]*)/g)) classes.add(cls[1]);
  }
  return classes;
}

function checkManualCoverage(appCssText, findings) {
  if (!existsSync(MANUAL)) {
    findings.push({ file: 'design-system.html', line: 1, rule: 'manual-coverage', detail: 'design manual is missing' });
    return;
  }
  const manual = readFileSync(MANUAL, 'utf8');
  for (const cls of appCssClasses(appCssText)) {
    if (!manual.includes(cls)) {
      findings.push({
        file: 'src/app.css', line: 1, rule: 'manual-coverage',
        detail: `.${cls} exists in app.css but is not shown in design-system.html — add a specimen`,
      });
    }
  }
}

function checkThemeParity(appCssText, findings) {
  const themes = {};
  for (const name of ['light', 'dark', 'contrast']) {
    const m = appCssText.match(new RegExp(`\\[data-theme='${name}'\\][^{]*\\{([\\s\\S]*?)\\n\\}`));
    themes[name] = new Set(m ? [...m[1].matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map((t) => t[1]) : []);
  }
  const all = new Set([...themes.light, ...themes.dark, ...themes.contrast]);
  for (const token of all) {
    const missing = ['light', 'dark', 'contrast'].filter((t) => !themes[t].has(token));
    if (missing.length > 0) {
      findings.push({
        file: 'src/app.css', line: 1, rule: 'theme-parity',
        detail: `${token} is missing in theme(s): ${missing.join(', ')}`,
      });
    }
  }
}

// ── main ────────────────────────────────────────────────────────────────────

export function runGuard() {
  const findings = [];
  const appCssText = readFileSync(APP_CSS, 'utf8');
  const files = walk(SRC).filter((f) => f !== APP_CSS);
  const assigned = collectAssignedTokens(files, appCssText);

  for (const file of files) {
    const rel = relative(WEB, file).replaceAll('\\', '/');
    const raw = readFileSync(file, 'utf8');
    const rawLines = raw.split('\n');
    const exemptLines = new Set();
    rawLines.forEach((l, i) => { if (l.includes('design-guard-exempt')) exemptLines.add(i + 1); });

    // undefined-token — whole file (markup style attrs consume tokens too)
    const noComments = stripCssComments(raw).replace(/<!--[\s\S]*?-->/g, blank);
    noComments.split('\n').forEach((line, i) => {
      if (exemptLines.has(i + 1)) return;
      for (const m of line.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)) {
        if (!assigned.has(m[1])) {
          findings.push({ file: rel, line: i + 1, rule: 'undefined-token', detail: `var(${m[1]}) — token is never defined; a shorthand using it silently drops the whole declaration` });
        }
      }
    });

    // emoji-icon — every icon comes from $lib/icons (ui-guardrails §14).
    // Pictographic emoji / ad-hoc glyphs standing in for a UI icon are banned
    // (beslut 2026-07-15: låsemoji förbjuden). Typographic arrows
    // (U+2190–21FF), middots and dashes are NOT icons and pass. Also blank JS
    // line comments so Swedish dev prose with a stray glyph never trips it.
    if (file.endsWith('.svelte')) {
      const noJsComments = noComments
        .split('\n')
        .map((line) => line.replace(/\/\/.*$/, ''))
        .join('\n');
      noJsComments.split('\n').forEach((line, i) => {
        if (exemptLines.has(i + 1)) return;
        const m = line.match(EMOJI_ICON);
        if (m) {
          findings.push({ file: rel, line: i + 1, rule: 'emoji-icon', detail: `"${m[0]}" — icons come from $lib/icons (Icon.svelte); no emoji/ad-hoc glyphs. Add the glyph to icons.ts and use <Icon name="…"/>` });
        }
      });
    }

    // value rules — style blocks
    const isCss = file.endsWith('.css');
    const blocks = isCss
      ? [{ css: raw, lineOffset: 0 }]
      : styleBlocks(raw);
    for (const block of blocks) {
      const css = stripCssComments(block.css);
      css.split('\n').forEach((line, i) => {
        const lineNo = block.lineOffset + i + 1;
        if (exemptLines.has(lineNo)) return;
        for (const [rule, detail] of checkCssLine(line)) {
          findings.push({ file: rel, line: lineNo, rule, detail });
        }
      });
      checkSelectors(css, block.lineOffset, rel, findings, exemptLines);
    }

    // value rules — inline style attributes in markup
    if (!isCss) {
      noComments.split('\n').forEach((line, i) => {
        if (exemptLines.has(i + 1)) return;
        for (const m of line.matchAll(/style\s*=\s*"([^"]*)"/g)) {
          for (const [rule, detail] of checkCssLine(m[1])) {
            findings.push({ file: rel, line: i + 1, rule, detail });
          }
        }
        // prose is serif — .ui (sans) never combines with lead/intro classes
        if (PROSE_UI.test(line)) {
          findings.push({ file: rel, line: i + 1, rule: 'prose-role', detail: 'intro/tagline/lead is prose — serif; .ui (sans) is for chrome only' });
        }
      });
    }
  }

  checkPageStructure(files, findings);

  checkManualCoverage(appCssText, findings);
  checkThemeParity(appCssText, findings);
  return findings;
}

// CLI
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const findings = runGuard();
  if (findings.length === 0) {
    console.log('design-guard: OK — no hardcoded CSS, manual in sync, themes complete.');
    process.exit(0);
  }
  const byRule = {};
  for (const f of findings) (byRule[f.rule] ??= []).push(f);
  for (const [rule, list] of Object.entries(byRule)) {
    console.error(`\n■ ${rule} (${list.length})`);
    for (const f of list) console.error(`  ${f.file}:${f.line}  ${f.detail}`);
  }
  console.error(`\ndesign-guard: ${findings.length} violation(s). Use the app.css primitives/tokens — or, in a genuinely exceptional case, add "design-guard-exempt: <reason>" on the line.`);
  process.exit(1);
}
