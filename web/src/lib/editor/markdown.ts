/** Pure markdown round-trip helpers for the definition editor.
 *
 * The WYSIWYG editor (TipTap + tiptap-markdown) speaks CommonMark-ish
 * markdown, while Kollepedia definitions use the markdown-lite dialect from
 * `$lib/text` (paragraphs, **bold**, *italic*, `[[crossref]]` — no escape
 * syntax). These two functions bridge the dialects so `renderMarkdown`,
 * `stripMarkdown` and the diff pipeline keep working on what we emit:
 *
 *   load:      md --preprocessMarkdown--> md with <span data-crossref> islands
 *              (parsed into crossref nodes by the editor schema, html: true)
 *   serialize: editor --tiptap-markdown--> md --postprocessMarkdown--> lite md
 */

/** Matches `[[target]]` and `[[target|label]]` (same shape as $lib/text). */
export const CROSSREF_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

/** Serialize a crossref back to its canonical markdown token. */
export function crossrefToMd(target: string, label?: string | null): string {
  return label && label !== target ? `[[${target}|${label}]]` : `[[${target}]]`;
}

function escapeAttr(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

/** Replace `[[…]]` tokens with inline-HTML islands the editor schema parses
 * into crossref nodes (tiptap-markdown must run with `html: true`). */
export function preprocessMarkdown(md: string): string {
  return md.replace(CROSSREF_RE, (_match, target: string, label?: string) => {
    const t = target.trim();
    const l = label?.trim() || null;
    const attrs =
      `data-crossref="" data-target="${escapeAttr(t)}"` +
      (l ? ` data-label="${escapeAttr(l)}"` : '');
    return `<span ${attrs}>${escapeAttr(`[[${l ?? t}]]`)}</span>`;
  });
}

/** The markdown-lite dialect has no escape syntax — strip the backslash
 * escapes prosemirror-markdown adds so `[[…]]`, `*`, `#`, `-` … come back
 * exactly as typed (crossref tokens typed as plain text stay renderable). */
export function postprocessMarkdown(md: string): string {
  return md.replace(/\\([\\`*_{}[\]()#+\-.!~>])/g, '$1');
}
