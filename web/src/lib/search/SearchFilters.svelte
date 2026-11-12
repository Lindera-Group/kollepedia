<script lang="ts">
  /** The home page's filter system (plan NG_TAXONOMIES §sökfilter).
   *
   * Collapsed: the two primary quick filters (Språk, Kategori) + "Fler
   * filter". Expanded: ONE panel where the primary filters take their
   * natural place among the rest (they never linger outside) — collections,
   * tags and status join them; "Dölj filter" collapses. An active-filter
   * summary line renders in BOTH states: values listed up to three per
   * type, then "4 valda". OR within a filter type, AND between types. */
  import { api, type TagCountOut, type TaxonomyOut } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { languageLabel, statusLabel, t } from '$lib/i18n.svelte';
  import MultiSelect from './MultiSelect.svelte';
  import { taxonomyValueName } from '$lib/taxonomy/valueName';
  import { STATUS_FILTER_VALUES } from './statuses';

  export interface SearchFilterState {
    language: string;
    categories: string[]; // taxonomy-value ids
    collections: string[]; // slugs
    tags: string[];
    statuses: string[];
  }

  interface Props {
    filters: SearchFilterState;
    onchange: (next: SearchFilterState) => void;
    /** Deep link: /?category_name=X preselects the matching value on load. */
    initialCategoryName?: string | null;
    /** Collection-page mode: the panel is prescoped to ONE collection — the
     * Samlingar group is hidden and tag suggestions are collection-local. */
    scopedCollection?: string | null;
  }

  let { filters, onchange, initialCategoryName = null, scopedCollection = null }: Props =
    $props();

  let open = $state(false);
  let categoryTaxonomy = $state<TaxonomyOut | null>(null);
  let collections = $state<{ slug: string; name: string }[]>([]);
  let topTags = $state<TagCountOut[]>([]);
  let appliedDeepLink = false;

  $effect(() => {
    api
      .taxonomies()
      .then((all) => {
        categoryTaxonomy = all.find((tx) => tx.slug === 'kategorier') ?? all[0] ?? null;
        if (!appliedDeepLink && initialCategoryName && categoryTaxonomy) {
          appliedDeepLink = true;
          const hit = categoryTaxonomy.values.find(
            (v) => v.name === initialCategoryName || v.name_en === initialCategoryName
          );
          if (hit) onchange({ ...filters, categories: [hit.id] });
        }
      })
      .catch(() => (categoryTaxonomy = null));
    if (!scopedCollection) {
      api
        .collections()
        .then((all) => (collections = all.map((c) => ({ slug: c.slug, name: c.name }))))
        .catch(() => (collections = []));
    }
    api
      .tagSuggestions('', scopedCollection ?? undefined)
      .then((tags) => (topTags = tags))
      .catch(() => (topTags = []));
  });

  const activeCount = $derived(
    (filters.language ? 1 : 0) +
      filters.categories.length +
      filters.collections.length +
      filters.tags.length +
      filters.statuses.length
  );

  function categoryName(id: string): string {
    const hit = categoryTaxonomy?.values.find((v) => v.id === id);
    return hit ? taxonomyValueName(hit) : id;
  }

  function collectionName(slug: string): string {
    return collections.find((c) => c.slug === slug)?.name ?? slug;
  }

  /** Aktiva filter som borttagbara piller (kontraktets princip 6 —
   * v1:s pillerhantering ersätter den gamla textsammanfattningen). */
  const activePills = $derived([
    ...(filters.language
      ? [{ label: languageLabel(filters.language), remove: () => set({ language: '' }) }]
      : []),
    ...filters.collections.map((slug) => ({
      label: collectionName(slug),
      remove: () => set({ collections: filters.collections.filter((s) => s !== slug) })
    })),
    ...filters.categories.map((id) => ({
      label: categoryName(id),
      remove: () => set({ categories: filters.categories.filter((c) => c !== id) })
    })),
    ...filters.tags.map((tag) => ({
      label: `#${tag}`,
      remove: () => set({ tags: filters.tags.filter((x) => x !== tag) })
    })),
    ...filters.statuses.map((status) => ({
      label: statusLabel(status),
      remove: () => set({ statuses: filters.statuses.filter((x) => x !== status) })
    }))
  ]);

  function set(partial: Partial<SearchFilterState>): void {
    onchange({ ...filters, ...partial });
  }

  function toggleIn(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
  }

  function clearAll(): void {
    onchange({ language: '', categories: [], collections: [], tags: [], statuses: [] });
  }
</script>

<div class="filters ui">
  {#if !open}
    <div class="quick">
      <div class="seg" role="group" aria-label={t('home.lang_filter_aria')}>
        {#each ['', 'sv', 'en'] as lang (lang)}
          <button
            type="button"
            class="seg-btn"
            aria-pressed={filters.language === lang}
            onclick={() => set({ language: lang })}
          >{lang ? lang.toUpperCase() : t('home.all_languages')}</button>
        {/each}
      </div>
      {#if !scopedCollection && collections.length > 0}
        <MultiSelect
          items={collections.map((c) => ({ value: c.slug, label: c.name }))}
          selected={filters.collections}
          placeholder={t('filters.type_collections')}
          onchange={(next) => set({ collections: next })}
        />
      {/if}
      {#if categoryTaxonomy}
        <MultiSelect
          items={categoryTaxonomy.values.map((v) => ({ value: v.id, label: taxonomyValueName(v) }))}
          selected={filters.categories}
          placeholder={t('filters.type_categories')}
          onchange={(next) => set({ categories: next })}
        />
      {/if}
      <button type="button" class="btn btn-quiet more" onclick={() => (open = true)} aria-expanded="false">
        {t('filters.more')}{#if activeCount > 0}&nbsp;<span class="count-badge">{activeCount}</span>{/if}
      </button>
    </div>
  {:else}
    <div class="panel card" role="group" aria-label={t('filters.panel_aria')}>
      <!-- Ingen rubrik: växlaren sitter kvar på Fler filter-knappens plats
           och byter bara etikett (beslut 2026-07-16). -->
      <div class="panel-head">
        <button type="button" class="btn btn-quiet" onclick={() => (open = false)} aria-expanded="true">
          {t('filters.hide')}{#if activeCount > 0}&nbsp;<span class="count-badge">{activeCount}</span>{/if}
        </button>
      </div>

      <div class="group">
        <span class="glabel" id="fl-lang">{t('filters.type_language')}</span>
        <div class="chips" role="group" aria-labelledby="fl-lang">
          {#each ['', 'sv', 'en'] as lang (lang)}
            <button
              type="button"
              class="filter-chip"
              aria-pressed={filters.language === lang}
              onclick={() => set({ language: lang })}
            >{lang ? languageLabel(lang) : t('home.all_languages')}</button>
          {/each}
        </div>
      </div>

      {#if categoryTaxonomy && categoryTaxonomy.values.length > 0}
        <div class="group">
          <span class="glabel" id="fl-cat">{t('filters.type_categories')}</span>
          <div class="chips" role="group" aria-labelledby="fl-cat">
            {#each categoryTaxonomy.values as value (value.id)}
              <button
                type="button"
                class="filter-chip"
                aria-pressed={filters.categories.includes(value.id)}
                onclick={() => set({ categories: toggleIn(filters.categories, value.id) })}
              >{taxonomyValueName(value)}</button>
            {/each}
          </div>
        </div>
      {/if}

      {#if topTags.length > 0}
        <div class="group">
          <span class="glabel" id="fl-tags">{t('filters.type_tags')}</span>
          <div class="chips" role="group" aria-labelledby="fl-tags">
            {#each topTags as tag (tag.name)}
              <button
                type="button"
                class="filter-chip"
                aria-pressed={filters.tags.includes(tag.name)}
                onclick={() => set({ tags: toggleIn(filters.tags, tag.name) })}
              >#{tag.name}</button>
            {/each}
          </div>
        </div>
      {/if}

      {#if !scopedCollection && collections.length > 0}
        <div class="group">
          <span class="glabel" id="fl-coll">{t('filters.type_collections')}</span>
          <div class="chips" role="group" aria-labelledby="fl-coll">
            {#each collections as coll (coll.slug)}
              <button
                type="button"
                class="filter-chip"
                aria-pressed={filters.collections.includes(coll.slug)}
                onclick={() => set({ collections: toggleIn(filters.collections, coll.slug) })}
              >{coll.name}</button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="group">
        <span class="glabel" id="fl-status">{t('filters.type_status')}</span>
        <div class="chips" role="group" aria-labelledby="fl-status">
          {#each STATUS_FILTER_VALUES as status (status)}
            <button
              type="button"
              class="filter-chip"
              aria-pressed={filters.statuses.includes(status)}
              onclick={() => set({ statuses: toggleIn(filters.statuses, status) })}
            >{statusLabel(status)}</button>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  {#if activeCount > 0}
    <div class="active-row" role="status">
      {#each activePills as pill (pill.label)}
        <button
          type="button"
          class="pill removable"
          onclick={pill.remove}
          aria-label={t('filters.remove_filter', { value: pill.label })}
        >
          {pill.label}
          <Icon name="close" size={11} />
        </button>
      {/each}
      <button type="button" class="btn btn-quiet clear" onclick={clearAll}>
        {t('filters.clear')}
      </button>
    </div>
  {/if}
</div>

<style>
  .quick {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  /* Segmenterad språkväljare — v1:s visuella modell (kontraktets princip 6):
     sammanfogade knappar, aktiv = bläckfylld. */
  .seg {
    display: inline-flex;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .seg-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    padding: 0.5em 0.9em;
    cursor: pointer;
    white-space: nowrap;
    border-inline-start: 1px solid var(--line);
    transition: background-color 0.15s, color 0.15s;
  }

  .seg-btn:first-child {
    border-inline-start: none;
  }

  .seg-btn:hover {
    color: var(--ink);
  }

  .seg-btn[aria-pressed='true'] {
    background: var(--ink);
    color: var(--bg);
  }

  .panel {
    margin-top: var(--space-2);
  }

  .panel-head {
    display: flex;
    align-items: center;
    margin-bottom: var(--space-3);
  }

  .group {
    margin-bottom: var(--space-3);
  }

  .glabel {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }


  .active-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: var(--space-2) 0 0;
  }

  /* Borttagbart filterpiller — hela pillret är knappen (v1:s FilterChip). */
  .removable {
    gap: 0.35em;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }

  .removable:hover,
  .removable:focus-visible {
    border-color: var(--del-strong);
    color: var(--del-strong);
  }

  .clear {
    font-size: var(--text-xs);
  }
</style>
