/** Inline atom node for `[[crossref]]` tokens, built on the Mention
 * extension for its Suggestion plumbing (trigger char `[[`).
 *
 * Round-trip contract: the node serializes to the exact `[[target]]` /
 * `[[target|label]]` markdown (via the tiptap-markdown storage spec below),
 * and incoming markdown is preprocessed by `preprocessMarkdown` into
 * `<span data-crossref …>` islands that `parseHTML` picks up. */
import type { Range } from '@tiptap/core';
import Mention, { type MentionOptions } from '@tiptap/extension-mention';
import type { Node as ProseMirrorNode, ResolvedPos } from '@tiptap/pm/model';
import type { SuggestionOptions } from '@tiptap/suggestion';
import type { ConceptListItem } from '$lib/api';
import { crossrefToMd } from './markdown';

export interface CrossrefAttrs {
  target: string;
  label: string | null;
}

/** Suggestion config shape for the crossref trigger (`editor` is injected). */
export type CrossrefSuggestion = Omit<SuggestionOptions<ConceptListItem, CrossrefAttrs>, 'editor'>;

/** Crossref-aware replacement for the default findSuggestionMatch: the query
 * runs from the last `[[` up to the caret (spaces allowed, any prefix) and
 * deactivates once the user closes the token with `]]` themselves. */
export function findCrossrefMatch(config: {
  $position: ResolvedPos;
}): { range: Range; query: string; text: string } | null {
  const { $position } = config;
  const node = $position.nodeBefore;
  const text = node?.isText ? (node.text ?? '') : '';
  const index = text.lastIndexOf('[[');
  if (index < 0) return null;
  const fragment = text.slice(index);
  if (fragment.includes(']]')) return null; // completed token — leave as plain text
  return {
    range: { from: $position.pos - text.length + index, to: $position.pos },
    query: fragment.slice(2),
    text: fragment
  };
}

interface MarkdownSerializerStateLike {
  write(content: string): void;
}

export const Crossref = Mention.extend<MentionOptions<ConceptListItem, CrossrefAttrs>>({
  name: 'crossref',

  addAttributes() {
    return {
      target: {
        default: '',
        parseHTML: (element: HTMLElement) => element.getAttribute('data-target') ?? '',
        renderHTML: (attributes: Record<string, unknown>) => ({
          'data-target': attributes.target
        })
      },
      label: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('data-label'),
        renderHTML: (attributes: Record<string, unknown>) =>
          attributes.label ? { 'data-label': attributes.label } : {}
      }
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-crossref]' }];
  },

  renderHTML({ node }) {
    const { target, label } = node.attrs as unknown as CrossrefAttrs;
    return [
      'span',
      {
        'data-crossref': '',
        'data-target': target,
        ...(label ? { 'data-label': label } : {}),
        class: 'crossref-chip'
      },
      `[[${label ?? target}]]`
    ];
  },

  renderText({ node }) {
    const { target, label } = node.attrs as unknown as CrossrefAttrs;
    return crossrefToMd(target, label);
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerStateLike, node: ProseMirrorNode) {
          const { target, label } = node.attrs as unknown as CrossrefAttrs;
          state.write(crossrefToMd(target, label));
        },
        parse: {
          // Incoming `[[…]]` tokens are turned into <span data-crossref>
          // islands by preprocessMarkdown before setContent — nothing to do.
        }
      }
    };
  }
});
