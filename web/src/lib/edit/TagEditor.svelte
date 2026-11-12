<script lang="ts">
  /** Pill editor for a version's tags: × to remove, Enter to add.
   *
   * Autosuggest (2026-07-11): existing tags are suggested as you type
   * (GET /tags) — suggestion-driven convergence: the vocabulary tightens
   * because editors SEE what already exists, not because free text is
   * forbidden. ARIA combobox pattern (ConceptCombobox precedent). */
  import { api, type TagCountOut } from '$lib/api';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    tags: string[];
    onchange: (tags: string[]) => void;
    disabled?: boolean;
    inputId?: string;
  }

  let { tags, onchange, disabled = false, inputId }: Props = $props();

  let draft = $state('');
  let suggestions = $state<TagCountOut[]>([]);
  let open = $state(false);
  let activeIndex = $state(-1);
  let debounce: ReturnType<typeof setTimeout> | undefined;
  let abort: AbortController | undefined;

  const listId = $derived(`${inputId ?? 'tags'}-listbox`);
  const visible = $derived(suggestions.filter((s) => !tags.includes(s.name)).slice(0, 8));

  function fetchSuggestions(q: string): void {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      abort?.abort();
      abort = new AbortController();
      api
        .tagSuggestions(q)
        .then((result) => {
          suggestions = result;
          open = result.length > 0;
          activeIndex = -1;
        })
        .catch(() => {
          /* suggestions are best-effort — typing works without them */
        });
    }, 150);
  }

  function add(tag = draft): void {
    const clean = tag.trim();
    draft = '';
    open = false;
    activeIndex = -1;
    if (!clean || tags.includes(clean)) return;
    onchange([...tags, clean]);
  }

  function remove(tag: string): void {
    onchange(tags.filter((t) => t !== tag));
  }

  function onInput(): void {
    if (draft.trim()) fetchSuggestions(draft.trim());
    else open = false;
  }

  function onKeydown(event: KeyboardEvent): void {
    if (open && event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, visible.length - 1);
    } else if (open && event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, -1);
    } else if (event.key === 'Escape' && open) {
      event.stopPropagation();
      open = false;
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (open && activeIndex >= 0 && visible[activeIndex]) add(visible[activeIndex].name);
      else add();
    } else if (event.key === 'Backspace' && draft === '' && tags.length > 0) {
      remove(tags[tags.length - 1]);
    }
  }

  function onBlur(): void {
    // Bengt #7: blur only closes the suggestions — adding a tag is an
    // EXPLICIT commit (Enter or clicking a suggestion), so tabbing away
    // never turns a discarded draft into a tag.
    setTimeout(() => (open = false), 120);
  }
</script>

<div class="tag-wrap">
  <div class="input tag-editor ui" class:disabled>
    {#each tags as tag (tag)}
      <span class="pill tag-chip">
        {tag}
        <button
          type="button"
          class="remove"
          onclick={() => remove(tag)}
          {disabled}
          aria-label={t('tags.remove_aria', { tag })}
        >×</button>
      </span>
    {/each}
    <input
      id={inputId}
      class="tag-draft"
      type="text"
      bind:value={draft}
      oninput={onInput}
      onkeydown={onKeydown}
      onblur={onBlur}
      {disabled}
      placeholder={tags.length ? t('tags.more_placeholder') : t('tags.add_placeholder')}
      aria-label={t('tags.add_aria')}
      role="combobox"
      aria-expanded={open}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
      autocomplete="off"
    />
  </div>
  {#if open && visible.length > 0}
    <ul class="suggestions card ui" id={listId} role="listbox" aria-label={t('tags.suggestions_aria')}>
      {#each visible as suggestion, i (suggestion.name)}
        <li
          id="{listId}-{i}"
          role="option"
          aria-selected={i === activeIndex}
          class:active={i === activeIndex}
        >
          <button type="button" onmousedown={(e) => { e.preventDefault(); add(suggestion.name); }}>
            {suggestion.name}
            <span class="count-badge">{suggestion.count}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .tag-wrap {
    position: relative;
  }

  /* The wrapper carries the .input recipe (composite widget) — the inner
     draft input below stays chromeless on purpose. */
  .tag-editor {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .tag-editor:focus-within {
    outline: 2px solid var(--focus);
    outline-offset: 1px;
  }

  .tag-editor.disabled {
    opacity: 0.6;
  }

  .tag-chip {
    gap: 0.35em;
  }

  .remove {
    border: none;
    background: none;
    padding: 0 0.1em;
    font-size: var(--text-sm);
    line-height: 1;
    color: var(--ink-3);
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .remove:hover {
    color: var(--del-strong);
  }

  .tag-draft {
    flex: 1;
    min-width: 160px;
    border: none;
    background: transparent;
    padding: 0.15em 0;
    color: var(--ink);
  }

  .tag-draft:focus {
    outline: none;
  }

  .suggestions {
    position: absolute;
    z-index: 30;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    max-height: 240px;
    overflow-y: auto;
    margin: 0;
    padding: var(--space-1);
    list-style: none;
  }

  .suggestions li button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-1) var(--space-2);
    border: none;
    background: transparent;
    color: var(--ink);
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .suggestions li.active button,
  .suggestions li button:hover {
    background: var(--accent-soft);
  }
</style>
