// @vitest-environment happy-dom
/** Round-trip guarantee for the definition editor: markdown loaded into the
 * real TipTap schema and serialized back must keep the markdown-lite dialect
 * intact — especially `[[crossref]]` tokens, which renderMarkdown /
 * stripMarkdown / the diff pipeline all parse from the raw markdown. */
import { describe, expect, it } from 'vitest';
import { Editor } from '@tiptap/core';
import { definitionExtensions, editorMarkdown } from './extensions';
import { preprocessMarkdown } from './markdown';

function roundtrip(md: string): string {
  const editor = new Editor({
    element: document.createElement('div'),
    extensions: definitionExtensions(),
    content: preprocessMarkdown(md)
  });
  try {
    return editorMarkdown(editor);
  } finally {
    editor.destroy();
  }
}

describe('definition editor markdown round-trip', () => {
  it('keeps [[target]] crossrefs byte-identical', () => {
    const md = 'Se även [[hållplats]] för detaljer.';
    expect(roundtrip(md)).toBe(md);
  });

  it('keeps [[target|label]] crossrefs byte-identical', () => {
    const md = 'En [[a|b]] mitt i texten, och [[bytespunkt|bytespunkten]] på slutet.';
    expect(roundtrip(md)).toBe(md);
  });

  it('keeps bold and italic', () => {
    const md = 'Detta är **fet** och *kursiv* text.';
    expect(roundtrip(md)).toBe(md);
  });

  it('keeps bullet and ordered lists', () => {
    const bullets = '- första punkten\n- andra punkten';
    const ordered = '1. ett\n2. två';
    expect(roundtrip(bullets)).toBe(bullets);
    expect(roundtrip(ordered)).toBe(ordered);
  });

  it('keeps plain multi-paragraph text unchanged', () => {
    const md = 'Första stycket om hållplatser.\n\nAndra stycket om resenärer.';
    expect(roundtrip(md)).toBe(md);
  });
});
