<script lang="ts">
  /** Debounced concept-search combobox (WAI-ARIA combobox pattern). */
  import { api, type ConceptListItem } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    onselect: (item: ConceptListItem) => void;
    excludeId?: string;
    disabled?: boolean;
    inputId?: string;
    /** Restrict hits to one language (iteration 3 — translation linking). */
    language?: string;
    /** Restrict hits to ONE collection (translation scope, 2026-07-12). */
    collection?: string;
  }

  let {
    onselect,
    excludeId,
    disabled = false,
    inputId = 'concept-combobox',
    language,
    collection
  }: Props = $props();

  let q = $state('');
  let items = $state<ConceptListItem[]>([]);
  let open = $state(false);
  let active = $state(-1);
  let searching = $state(false);
  let searchError = $state<string | null>(null);

  let timer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const query = q.trim();
    clearTimeout(timer);
    if (!query) {
      items = [];
      open = false;
      searching = false;
      searchError = null;
      return;
    }
    searching = true;
    timer = setTimeout(() => {
      api
        .concepts({ q: query, language, collection, limit: 8 })
        .then((r) => {
          items = r.items.filter((item) => item.id !== excludeId);
          open = true;
          active = items.length ? 0 : -1;
          searching = false;
          searchError = null;
        })
        .catch((e) => {
          searching = false;
          searchError = errorMessage(e);
        });
    }, 220);
  });

  function choose(item: ConceptListItem): void {
    onselect(item);
    q = '';
    items = [];
    open = false;
    active = -1;
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!open || items.length === 0) {
      if (event.key === 'Escape') open = false;
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      active = (active + 1) % items.length;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      active = (active - 1 + items.length) % items.length;
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (active >= 0) choose(items[active]);
    } else if (event.key === 'Escape') {
      open = false;
    }
  }
</script>

<div class="combobox ui">
  <input
    id={inputId}
    class="input"
    type="text"
    role="combobox"
    aria-expanded={open}
    aria-controls="{inputId}-listbox"
    aria-activedescendant={active >= 0 ? `${inputId}-option-${active}` : undefined}
    aria-autocomplete="list"
    autocomplete="off"
    spellcheck="false"
    placeholder={t('combo.placeholder')}
    bind:value={q}
    onkeydown={onKeydown}
    onblur={() => setTimeout(() => (open = false), 120)}
    {disabled}
  />
  {#if searching}
    <span class="state mono" aria-hidden="true">{t('combo.searching')}</span>
  {/if}

  {#if open}
    <ul class="listbox card" id="{inputId}-listbox" role="listbox" aria-label={t('combo.listbox_aria')}>
      {#each items as item, i (item.id)}
        <li
          id="{inputId}-option-{i}"
          role="option"
          aria-selected={i === active}
          class:active={i === active}
        >
          <button
            type="button"
            tabindex="-1"
            onmousedown={(e) => {
              e.preventDefault();
              choose(item);
            }}
            onmouseenter={() => (active = i)}
          >
            <span class="form">{item.canonical_form}</span>
            <span class="coll mono">{item.collection_name}{item.collection_year ? ` · ${item.collection_year}` : ''}</span>
          </button>
        </li>
      {:else}
        <li class="empty" role="option" aria-selected="false" aria-disabled="true">{t('combo.no_hits')}</li>
      {/each}
    </ul>
  {/if}

  {#if searchError}
    <p class="error" role="alert">{t('combo.search_failed', { error: searchError })}</p>
  {/if}
</div>

<style>
  .combobox {
    position: relative;
  }

  input {
    width: 100%;
  }

  .state {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    color: var(--ink-3);
  }

  .listbox {
    position: absolute;
    top: calc(100% + var(--space-1));
    left: 0;
    right: 0;
    z-index: 40;
    margin: 0;
    padding: var(--space-2);
    list-style: none;
    max-height: 320px;
    overflow-y: auto;
    box-shadow: var(--shadow-md);
  }

  .listbox li {
    border-radius: var(--radius-sm);
  }

  .listbox li.active {
    background: var(--accent-soft);
  }

  .listbox button {
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

  .error {
    margin: var(--space-1) 0 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }
</style>
