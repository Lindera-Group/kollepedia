/** Shared TipTap configuration for definition editing — used by both the
 * DefinitionEditor component and the round-trip tests so they exercise the
 * exact same schema and markdown pipeline. */
import type { AnyExtension, Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import { Crossref, type CrossrefSuggestion } from './crossref';
import { postprocessMarkdown } from './markdown';

/** Editor extensions for the markdown-lite definition dialect: paragraphs,
 * bold/italic, bullet/ordered lists, hard breaks and [[crossref]] nodes.
 * Headings, blockquotes, code, strike and rules are OFF by design.
 * `history: false` is required in collab mode — the Collaboration extension
 * ships its own y-undo undo/redo, which conflicts with prosemirror-history. */
export function definitionExtensions(
  suggestion?: CrossrefSuggestion,
  options?: { history?: boolean }
): AnyExtension[] {
  return [
    StarterKit.configure({
      heading: false,
      blockquote: false,
      code: false,
      codeBlock: false,
      strike: false,
      horizontalRule: false,
      ...(options?.history === false ? { history: false } : {})
    }),
    Markdown.configure({
      html: true, // required: preprocessMarkdown injects <span data-crossref> islands
      breaks: true, // single \n ⇄ hard break, like renderMarkdown's <br />
      tightLists: true
    }),
    suggestion ? Crossref.configure({ suggestion }) : Crossref
  ];
}

/** Serialize the editor document back to markdown-lite. */
export function editorMarkdown(editor: Editor): string {
  const storage = editor.storage.markdown as { getMarkdown(): string };
  return postprocessMarkdown(storage.getMarkdown());
}
