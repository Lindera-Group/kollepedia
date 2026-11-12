<script lang="ts">
  /** TipTap markdown WYSIWYG for definition fields (ROADMAP iteration 3).
   * Markdown in / markdown out — `[[crossref]]` tokens round-trip byte-
   * identically so renderMarkdown/stripMarkdown/diff keep working. Crossrefs
   * are inserted via a `[[`-triggered suggestion popup backed by
   * api.concepts. A plain-textarea fallback ("Redigera som text") stays one
   * toggle away as the safety hatch. */
  import { untrack } from 'svelte';
  import { Editor } from '@tiptap/core';
  import Collaboration from '@tiptap/extension-collaboration';
  import CollaborationCursor from '@tiptap/extension-collaboration-cursor';
  import type { SuggestionKeyDownProps, SuggestionProps } from '@tiptap/suggestion';
  import { api, type ConceptListItem } from '$lib/api';
  import type { EditorCollab } from '$lib/collab/session.svelte';
  import { t } from '$lib/i18n.svelte';
  import { findCrossrefMatch, type CrossrefAttrs } from './crossref';
  import { definitionExtensions, editorMarkdown } from './extensions';
  import { preprocessMarkdown } from './markdown';

  interface Props {
    /** Markdown-lite source of truth (paragraphs, **fet**, *kursiv*, [[crossref]]). */
    value: string;
    onchange: (md: string) => void;
    disabled?: boolean;
    placeholder?: string;
    /** id of the editable region, so an external <label for> can reference it. */
    inputId?: string;
    /** Realtime co-editing: bind TipTap to a shared Y.XmlFragment instead of
     * the markdown `value` (which stays the SERIALIZATION output — onchange
     * keeps firing for local and remote transactions alike). */
    collab?: EditorCollab | null;
  }

  let {
    value,
    onchange,
    disabled = false,
    placeholder = '',
    inputId = 'definition-editor',
    collab = null
  }: Props = $props();

  let element = $state<HTMLElement | null>(null);
  let editor = $state.raw<Editor | null>(null);
  let rawMode = $state(false);

  /** Last markdown either emitted by the editor or synced in — guards the
   * value-prop effect against feeding our own output back into TipTap. */
  let lastSynced: string | null = null;

  // Toolbar/content state mirrored out of TipTap on each transaction.
  let boldActive = $state(false);
  let italicActive = $state(false);
  let bulletActive = $state(false);
  let orderedActive = $state(false);
  let isEmpty = $state(true);

  // Crossref suggestion popup (driven by the Suggestion plugin callbacks).
  let sugOpen = $state(false);
  let sugItems = $state<ConceptListItem[]>([]);
  let sugActive = $state(0);
  let sugQuery = $state('');
  let sugPos = $state({ left: 0, top: 0 });
  let sugCommand: ((attrs: CrossrefAttrs) => void) | null = null;
  let sugDismissed = false;

  async function fetchSuggestions({ query }: { query: string }): Promise<ConceptListItem[]> {
    const q = query.trim();
    if (!q) return [];
    try {
      const result = await api.concepts({ q, limit: 6 });
      return result.items;
    } catch {
      return []; // popup shows "Inga träffar" — the safety hatch is plain [[text]]
    }
  }

  function updateSuggestion(props: SuggestionProps<ConceptListItem, CrossrefAttrs>): void {
    sugItems = props.items ?? [];
    sugQuery = props.query;
    sugActive = 0;
    sugCommand = props.command;
    const rect = props.clientRect?.();
    const host = element?.getBoundingClientRect();
    if (rect && host) {
      const width = Math.max(host.width, 300);
      sugPos = {
        left: Math.max(0, Math.min(rect.left - host.left, width - 300)),
        top: rect.bottom - host.top + 6
      };
    }
    sugOpen = !sugDismissed;
  }

  function onSuggestionKeyDown({ event }: SuggestionKeyDownProps): boolean {
    if (event.key === 'Escape') {
      if (!sugOpen) return false;
      sugDismissed = true;
      sugOpen = false;
      return true;
    }
    if (!sugOpen || sugItems.length === 0) return false;
    if (event.key === 'ArrowDown') {
      sugActive = (sugActive + 1) % sugItems.length;
      return true;
    }
    if (event.key === 'ArrowUp') {
      sugActive = (sugActive - 1 + sugItems.length) % sugItems.length;
      return true;
    }
    if (event.key === 'Enter') {
      chooseSuggestion(sugItems[sugActive]);
      return true;
    }
    return false;
  }

  function chooseSuggestion(item: ConceptListItem): void {
    sugCommand?.({ target: item.canonical_form, label: null });
    closeSuggestion();
  }

  function closeSuggestion(): void {
    sugOpen = false;
    sugItems = [];
    sugQuery = '';
    sugActive = 0;
    sugCommand = null;
    sugDismissed = false;
  }

  // Mount TipTap on the shell element (recreated when leaving raw mode, and
  // when collab turns on/off — the session appearing/falling back to solo).
  $effect(() => {
    const host = element;
    const shared = collab; // tracked: remount on session hand-over
    if (!host) return;
    const initial = untrack(() => value);
    const instance = new Editor({
      element: host,
      editable: untrack(() => !disabled),
      // In collab mode the Collaboration extension owns the document — the
      // initial content must NOT be set here (the first peer seeds the
      // fragment post-sync instead, see the seed effect below).
      ...(shared ? {} : { content: preprocessMarkdown(initial) }),
      extensions: [
        ...definitionExtensions(
          {
            char: '[[',
            allowSpaces: true,
            allowedPrefixes: null,
            findSuggestionMatch: findCrossrefMatch,
            items: fetchSuggestions,
            render: () => ({
              onStart: (props) => {
                sugDismissed = false;
                updateSuggestion(props);
              },
              onUpdate: updateSuggestion,
              onKeyDown: onSuggestionKeyDown,
              onExit: closeSuggestion
            })
          },
          shared ? { history: false } : undefined
        ),
        ...(shared
          ? [
              Collaboration.configure({ fragment: shared.fragment }),
              CollaborationCursor.configure({ provider: shared.provider, user: shared.user })
            ]
          : [])
      ],
      editorProps: {
        attributes: {
          id: inputId,
          role: 'textbox',
          'aria-multiline': 'true',
          ...(placeholder ? { 'aria-placeholder': placeholder } : {})
        }
      },
      onTransaction: ({ editor: ed }) => {
        boldActive = ed.isActive('bold');
        italicActive = ed.isActive('italic');
        bulletActive = ed.isActive('bulletList');
        orderedActive = ed.isActive('orderedList');
        isEmpty = ed.isEmpty;
      },
      onUpdate: ({ editor: ed }) => {
        const md = editorMarkdown(ed);
        lastSynced = md;
        onchange(md);
      }
    });
    lastSynced = initial;
    isEmpty = instance.isEmpty;
    editor = instance;
    return () => {
      instance.destroy();
      editor = null;
      closeSuggestion();
    };
  });

  // First-peer fragment seeding: once the session decides the room is fresh
  // (fields map empty post-sync) the shared fragment is populated through the
  // bound editor — one Yjs transaction via the Collaboration binding. The
  // re-check of fragment emptiness narrows the two-first-peers race.
  $effect(() => {
    const shared = collab;
    const ed = editor;
    if (!shared || !ed) return;
    const md = shared.seedMarkdown; // reactive via the session getter
    if (md == null) return;
    if (shared.fragment.length === 0) {
      ed.commands.setContent(preprocessMarkdown(md), true);
    }
    shared.confirmSeed();
  });

  // Sync external value changes into the editor (e.g. parent resets).
  // Not in collab mode: there the shared doc is the source of truth and
  // setContent would clobber concurrent edits.
  $effect(() => {
    const next = value;
    const ed = editor;
    if (collab || !ed || next === lastSynced) return;
    lastSynced = next;
    ed.commands.setContent(preprocessMarkdown(next), false);
  });

  $effect(() => {
    editor?.setEditable(!disabled);
  });

  function toggleRaw(): void {
    rawMode = !rawMode;
    if (rawMode) closeSuggestion();
  }
</script>

<div class="defed">
  <div class="toolbar ui" role="toolbar" aria-label={t('editor.toolbar_aria')}>
    {#if !rawMode}
      <button
        type="button"
        class="btn btn-quiet tb"
        aria-pressed={boldActive}
        aria-label={t('editor.bold')}
        title={t('editor.bold_title')}
        {disabled}
        onclick={() => editor?.chain().focus().toggleBold().run()}
      >
        <strong>B</strong>
      </button>
      <button
        type="button"
        class="btn btn-quiet tb"
        aria-pressed={italicActive}
        aria-label={t('editor.italic')}
        title={t('editor.italic_title')}
        {disabled}
        onclick={() => editor?.chain().focus().toggleItalic().run()}
      >
        <em>I</em>
      </button>
      <button
        type="button"
        class="btn btn-quiet tb"
        aria-pressed={bulletActive}
        title={t('editor.bullet_list')}
        {disabled}
        onclick={() => editor?.chain().focus().toggleBulletList().run()}
      >
        • {t('editor.bullet_list')}
      </button>
      <button
        type="button"
        class="btn btn-quiet tb"
        aria-pressed={orderedActive}
        title={t('editor.ordered_list_title')}
        {disabled}
        onclick={() => editor?.chain().focus().toggleOrderedList().run()}
      >
        1. {t('editor.ordered_list_btn')}
      </button>
    {/if}
    <span class="spacer"></span>
    <button
      type="button"
      class="btn btn-quiet tb"
      aria-pressed={rawMode}
      title={t('editor.raw_toggle_title')}
      onclick={toggleRaw}
    >
      {rawMode ? t('editor.visual_mode') : t('editor.raw_mode')}
    </button>
  </div>

  {#if rawMode}
    <!-- In collab mode the textarea is read-only: two-way textarea ⇄ Yjs sync
         is out of scope, so text mode becomes a live markdown VIEW of the
         shared doc (value keeps updating from remote transactions). -->
    <textarea
      id={inputId}
      class="raw"
      rows="8"
      {disabled}
      readonly={!!collab}
      {placeholder}
      spellcheck="true"
      {value}
      oninput={(event) => {
        if (collab) return;
        lastSynced = event.currentTarget.value;
        onchange(event.currentTarget.value);
      }}
    ></textarea>
    {#if collab}
      <p class="raw-hint ui" role="note">{t('rt.textarea_disabled_hint')}</p>
    {/if}
  {:else}
    <div class="shell" class:disabled bind:this={element}>
      {#if isEmpty && placeholder}
        <div class="placeholder" aria-hidden="true">{placeholder}</div>
      {/if}

      {#if sugOpen}
        <ul
          class="sug card ui"
          role="listbox"
          aria-label={t('editor.sug_aria')}
          style="left: {sugPos.left}px; top: {sugPos.top}px"
        >
          {#each sugItems as item, i (item.id)}
            <li role="option" aria-selected={i === sugActive} class:active={i === sugActive}>
              <button
                type="button"
                tabindex="-1"
                onmousedown={(event) => {
                  event.preventDefault();
                  chooseSuggestion(item);
                }}
                onmouseenter={() => (sugActive = i)}
              >
                <span class="form">{item.canonical_form}</span>
                <span class="coll mono"
                  >{item.collection_name}{item.collection_year
                    ? ` · ${item.collection_year}`
                    : ''}</span
                >
              </button>
            </li>
          {:else}
            <li class="empty" role="option" aria-selected="false" aria-disabled="true">
              {sugQuery.trim() ? t('combo.no_hits') : t('editor.sug_type_to_search')}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</div>

<style>
  .defed {
    position: relative;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-bottom: var(--space-1);
  }

  .spacer {
    flex: 1;
  }

  .tb {
    padding: 0.25em 0.6em;
    font-size: var(--text-xs);
  }

  .tb[aria-pressed='true'] {
    background: var(--accent-soft);
    color: var(--accent);
  }

  .shell {
    position: relative;
  }

  /* The contenteditable body — styled to match .tm-def / the old textarea. */
  .shell :global(.tiptap) {
    min-height: 10rem;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-serif);
    font-size: var(--text-body-lg);
    line-height: 1.75;
  }

  .shell.disabled :global(.tiptap) {
    background: var(--bg-sunken);
    color: var(--ink-3);
    cursor: not-allowed;
  }

  .shell :global(.tiptap p) {
    margin: 0 0 var(--space-3);
  }

  .shell :global(.tiptap > :last-child) {
    margin-bottom: 0;
  }

  .shell :global(.tiptap ul),
  .shell :global(.tiptap ol) {
    margin: 0 0 var(--space-3);
    padding-left: 1.4em;
  }

  /* Crossref chip: accent underline, rendered as [[label]]. */
  .shell :global(.crossref-chip) {
    color: var(--accent);
    background: var(--accent-soft);
    border-bottom: 1px solid var(--accent);
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    padding: 0 0.12em;
  }

  /* The in-progress `[[query` text while the suggestion is active. */
  .shell :global(.suggestion) {
    color: var(--accent);
    background: var(--accent-soft);
    border-radius: var(--radius-sm);
  }

  /* CollaborationCursor: remote carets + name labels. The extension sets
     border-color/background-color inline from each peer's palette colour
     (white label text — the palette guarantees ≥ 4.5:1 contrast). */
  .shell :global(.collaboration-cursor__caret) {
    position: relative;
    margin-left: -1px;
    margin-right: -1px;
    border-left: 1px solid;
    border-right: 1px solid;
    word-break: normal;
    pointer-events: none;
  }

  .shell :global(.collaboration-cursor__label) {
    position: absolute;
    top: -1.35em;
    left: -1px;
    padding: 0.05em 0.4em;
    border-radius: var(--radius-sm) var(--radius-sm) var(--radius-sm) 0;
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-style: normal;
    font-weight: 600;
    line-height: 1.3;
    color: var(--on-accent);
    white-space: nowrap;
    user-select: none;
    pointer-events: none;
  }

  .placeholder {
    position: absolute;
    top: var(--space-2);
    left: var(--space-3);
    right: var(--space-3);
    pointer-events: none;
    font-family: var(--font-serif);
    font-size: var(--text-body-lg);
    line-height: 1.75;
    color: var(--ink-3);
  }

  .sug {
    position: absolute;
    z-index: 40;
    width: 300px;
    max-height: 320px;
    overflow-y: auto;
    margin: 0;
    padding: var(--space-2);
    list-style: none;
    box-shadow: var(--shadow-md);
  }

  .sug li {
    border-radius: var(--radius-sm);
  }

  .sug li.active {
    background: var(--accent-soft);
  }

  .sug button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.15em;
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: none;
    background: none;
    text-align: left;
    cursor: pointer;
    color: var(--ink);
    border-radius: var(--radius-sm);
  }

  .form {
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .coll {
    color: var(--ink-3);
  }

  .empty {
    padding: var(--space-2) var(--space-3);
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .raw {
    width: 100%;
    min-height: 10rem;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-serif);
    font-size: var(--text-body-lg);
    line-height: 1.6;
    resize: vertical;
  }

  .raw[readonly] {
    background: var(--bg-sunken);
    color: var(--ink-3);
  }

  .raw-hint {
    margin: var(--space-1) 0 0;
    font-size: var(--text-xs);
    color: var(--ink-3);
  }
</style>
