<script lang="ts">
  /** THE search surface (ui-guardrails §16 harmonisation): one serif
   * search input + the SearchFilters system, identical on the home page and
   * the collection page (prescoped there). Pages own the query/filter state;
   * this component owns the look. */
  import SearchFilters, { type SearchFilterState } from './SearchFilters.svelte';

  interface Props {
    q: string;
    filters: SearchFilterState;
    onchange: (next: SearchFilterState) => void;
    placeholder: string;
    ariaLabel: string;
    scopedCollection?: string | null;
    initialCategoryName?: string | null;
  }

  let {
    q = $bindable(''),
    filters,
    onchange,
    placeholder,
    ariaLabel,
    scopedCollection = null,
    initialCategoryName = null
  }: Props = $props();
</script>

<div class="searchbar ui">
  <div class="search-row">
    <input class="input search-input" type="search" {placeholder} bind:value={q} aria-label={ariaLabel} />
  </div>
  <SearchFilters {filters} {onchange} {scopedCollection} {initialCategoryName} />
</div>

<style>
  /* Balanced air above and below (the hero stats line was removed for this). */
  .searchbar {
    margin: var(--space-8) 0;
    max-width: 620px;
  }

  .search-row {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  /* THE search field — deliberately bigger than the .input base recipe:
     serif, larger type, more air, stronger line, softer corners. */
  .search-input {
    flex: 1;
    min-width: 0;
    font-size: var(--text-lg);
    font-family: var(--font-serif);
    padding: var(--space-3) var(--space-4);
    border-color: var(--line-strong);
    border-radius: var(--radius-lg);
  }

  .search-input::placeholder {
    color: var(--ink-3);
  }
</style>
