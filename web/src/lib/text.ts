/** Markdown-lite rendering + plain-text extraction for the Time Machine. */

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

/** Link targets a `[label](target)` may point at: web and mail URLs, same-site
 * paths and `#concept` anchors. Anything else (`javascript:`, `data:`,
 * `vbscript:`, …) is left as text: definitions are user-written and rendered
 * with {@html}, so an unlisted scheme would be stored XSS. */
const SAFE_LINK_TARGET = /^(https?:|mailto:|\/|#)/i;

/** Targets that leave the site: absolute http(s) and protocol-relative URLs. */
const EXTERNAL_LINK_TARGET = /^(https?:|\/\/)/i;

/** Inline markup within a block: escape, then [[cross-refs]], [label](target)
 * links (concept anchors, external, internal), bold and italic. */
function inline(text: string): string {
  let html = escapeHtml(text);
  html = html.replace(
    /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_m, target: string, label?: string) =>
      `<a href="/?q=${encodeURIComponent(target.trim())}" class="crossref">${label ?? target}</a>`
  );
  // Standard markdown links: [Label](#concept-id) → concept link (the
  // Transmodel import writes these), [Label](https://…) → external link,
  // [Label](/path) → internal link. `match` is already HTML-escaped (the whole
  // block was escaped above), so returning it renders the markdown as text.
  html = html.replace(/\[([^\]]+)\]\(([^()\s]+)\)/g, (match, label: string, raw: string) => {
    const target = raw.trim();
    if (!SAFE_LINK_TARGET.test(target)) return match;
    if (target.startsWith('#')) {
      return `<a href="/concepts/${target.slice(1)}" class="crossref">${label}</a>`;
    }
    if (EXTERNAL_LINK_TARGET.test(target)) {
      return `<a href="${target}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    }
    return `<a href="${target}">${label}</a>`;
  });
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
  return html;
}

/** Render markdown to safe HTML: `##` headings, bullet/numbered lists,
 * paragraphs, bold/italic, external + concept links and [[cross-refs]].
 * Used for concept definitions and the rich collection descriptions. */
export function renderMarkdown(md: string): string {
  const out: string[] = [];
  for (const raw of md.split(/\n{2,}/)) {
    const block = raw.trim();
    if (!block) continue;
    const lines = block.split('\n');

    // Heading (## Title): the first line; any remainder is a following paragraph.
    const heading = lines[0].match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = Math.min(heading[1].length, 6);
      out.push(`<h${level}>${inline(heading[2].trim())}</h${level}>`);
      const rest = lines.slice(1).join('\n').trim();
      if (rest) out.push(`<p>${inline(rest).replace(/\n/g, '<br />')}</p>`);
      continue;
    }

    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      const items = lines.map((line) => `<li>${inline(line.replace(/^\s*[-*]\s+/, ''))}</li>`).join('');
      out.push(`<ul>${items}</ul>`);
      continue;
    }

    if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
      const items = lines.map((line) => `<li>${inline(line.replace(/^\s*\d+\.\s+/, ''))}</li>`).join('');
      out.push(`<ol>${items}</ol>`);
      continue;
    }

    out.push(`<p>${inline(block).replace(/\n/g, '<br />')}</p>`);
  }
  return out.join('\n');
}

/** Strip markdown to the plain prose the Time Machine animates. */
export function stripMarkdown(md: string): string {
  return md
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '$2')
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/\[([^\]]+)\]\(([^()\s]+)\)/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1$2')
    .replace(/^#+\s*/gm, '')
    .replace(/\r/g, '')
    .trim();
}

// Locale-aware helpers now live in the i18n module (they follow the UI
// language); re-exported here so existing `$lib/text` imports keep working.
export { formatDate, formatNumber, languageLabel, statusLabel } from './i18n.svelte';

export function formatYear(iso: string): string {
  return String(new Date(iso).getFullYear());
}
