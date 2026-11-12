<script lang="ts">
  import { untrack } from 'svelte';
  import { page } from '$app/state';
  import { api, night4, type ConceptListItem, type MostWatchedItem } from '$lib/api';
  import ConceptCard from '$lib/components/ConceptCard.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import SearchBar from '$lib/search/SearchBar.svelte';
  import { type SearchFilterState } from '$lib/search/SearchFilters.svelte';
  import { ConceptBrowser } from '$lib/components/conceptBrowser.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { hasMore } from '$lib/components/infiniteList';
  import { formatNumber, languageLabel, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import type { PageProps, Snapshot } from './$types';

  let { data }: PageProps = $props();

  let q = $state(page.url.searchParams.get('q') ?? '');
  // The full filter state (plan NG_TAXONOMIES §sökfilter): OR within a type,
  // AND between types. `language` lives inside it; SearchFilters renders both
  // the quick row and the expanded panel over this single object.
  let filters = $state<SearchFilterState>({
    language: '',
    categories: [],
    collections: [],
    tags: [],
    statuses: []
  });
  const initialCategoryName = page.url.searchParams.get('category_name');

  // The main list is the *browse* of every concept (seeded server-side) that
  // the search field + filters narrow in place — one accumulating
  // infinite-scroll list driven by the shared ConceptBrowser engine.
  type HomeParams = { q: string; filters: SearchFilterState };
  // svelte-ignore state_referenced_locally — the browser is seeded once at mount by design.
  const browseSeed = data.browse;
  const browser = new ConceptBrowser<HomeParams>({
    fetchPage: (params, offset, limit) =>
      api.concepts({
        q: params.q || undefined,
        language: params.filters.language || undefined,
        category: params.filters.categories.join(',') || undefined,
        collection: params.filters.collections.join(',') || undefined,
        tag: params.filters.tags.join(',') || undefined,
        status: params.filters.statuses.join(',') || undefined,
        limit,
        offset
      }),
    sameParams: (a, b) => a.q === b.q && JSON.stringify(a.filters) === JSON.stringify(b.filters),
    seed: browseSeed
      ? {
          params: {
            q: '',
            filters: { language: '', categories: [], collections: [], tags: [], statuses: [] }
          },
          page: browseSeed
        }
      : null
  });

  // "Mest bevakade" teaser — top watched concepts, visibility-filtered
  // server-side. Hidden entirely until the backend delivers a non-empty list.
  let mostWatched = $state<MostWatchedItem[]>([]);
  $effect(() => {
    night4
      .mostWatched(5)
      .then((list) => (mostWatched = list))
      .catch(() => (mostWatched = []));
  });

  // Position memory: capture the accumulated list when navigating away;
  // restore() runs before render on history back (see conceptBrowser.svelte.ts
  // for the hand-rolled scrollY rationale).
  type HomeSnapshot = {
    q: string;
    filters: SearchFilterState;
    list: ReturnType<ConceptBrowser<HomeParams>['capture']>;
    scrollY: number;
  };
  export const snapshot: Snapshot<HomeSnapshot> = {
    capture: () => ({
      q,
      filters: $state.snapshot(filters),
      list: browser.capture(),
      scrollY: window.scrollY
    }),
    restore: (value) => {
      q = value.q;
      filters = value.filters;
      browser.restore(value.list);
      requestAnimationFrame(() => scrollTo(0, value.scrollY));
    }
  };

  // The restore flag only applies to the sentinel mounted in the first
  // render — later sentinel re-creations (new search) must not skip.
  $effect(() => {
    browser.restoredFromSnapshot = false;
  });

  // Stats + the Time-Machine teaser are seeded by +page.ts (SSR + client nav);
  // the full collections list now lives on /collections.
  const stats = $derived(data.stats);
  const activeFilterCount = $derived(
    (filters.language ? 1 : 0) +
      filters.categories.length +
      filters.collections.length +
      filters.tags.length +
      filters.statuses.length
  );
  const loadError = $derived(data.loadError);

  /** The zero-hit state's secondary action: back to the full browse. */
  function clearSearch(): void {
    q = '';
    filters = { language: '', categories: [], collections: [], tags: [], statuses: [] };
  }

  $effect(() => {
    const query = q.trim();
    const f = $state.snapshot(filters) as SearchFilterState;
    untrack(() => browser.reset({ q: query, filters: f }, { debounceMs: query ? 220 : 0 }));
  });
</script>

<svelte:head>
  <title>{t('home.head_title')}</title>
  <meta name="description" content={t('home.tagline')} />
</svelte:head>

<div class="container">
  <section class="hero">
    <h1>{t('home.hero_1')}<br />{t('home.hero_2')}</h1>
    <p class="tagline">{t('home.tagline')}</p>

    <SearchBar
      bind:q
      {filters}
      {initialCategoryName}
      placeholder={t('home.search_placeholder')}
      ariaLabel={t('home.search_aria')}
      onchange={(next) => (filters = next)}
    />
  </section>

  {#if loadError}
    <p class="error ui">{t('home.api_error', { error: loadError })}</p>
  {/if}

  {#if !q.trim()}
    <!-- Mest bevakade only (2026-07-12): the Historik/Samlingar teasers were
         bloat — history is reached from every concept, collections from the
         menu. The term list below is the main content. -->
    <section class="secondary">
      {#if mostWatched.length > 0}
        <div class="teaser mw-teaser">
          <span class="teaser-kicker mono">{t('mw.kicker')}</span>
          <ul class="mw-list ui">
            {#each mostWatched as mw (mw.id)}
              <li>
                <a href="/concepts/{mw.id}">{mw.canonical_form}</a>
                <span
                  class="mw-count"
                  aria-label={t('mw.watchers_aria', { count: mw.watcher_count })}
                >
                  <Icon name="bell" size={11} />
                  <span class="count-badge">{mw.watcher_count}</span>
                </span>
              </li>
            {/each}
          </ul>
          <a class="teaser-cta ui" href="/most-watched">{t('mw.all_link')}</a>
        </div>
      {/if}
    </section>
  {/if}

  <section class="results">
    <h2 class="section-title">
      {#if browser.searching}
        {t('common.searching')}
      {:else if browser.total !== null}
        {q.trim() || activeFilterCount > 0
          ? t('home.hits', { count: formatNumber(browser.total) })
          : t('home.hits_all', { count: formatNumber(browser.total) })}
      {/if}
    </h2>
    <div class="card-grid">
      {#each browser.items as concept (concept.id)}
        <ConceptCard {concept} />
      {/each}
    </div>
    {#if !browser.searching && browser.total === 0}
      <!-- Zero-hit path forward (paket D2, v1:s Algolia/Notion-mönster):
           the create chip appears ONLY at exactly zero hits (never on
           partial results, to avoid duplicate concepts) and only signed-in. -->
      <EmptyState
        icon="search"
        heading={t('empty.no_hits_h')}
        body={q.trim()
          ? t('empty.no_hits_for', { query: q.trim() })
          : t('empty.no_hits_filters')}
      >
        {#snippet actions()}
          {#if q.trim() && currentUser.handle}
            <a
              class="btn-primary"
              href="/new-concept?name={encodeURIComponent(q.trim())}"
              data-testid="create-from-search"
            >
              {t('empty.create_from_search', { query: q.trim() })}
            </a>
          {/if}
          <button type="button" class="btn" onclick={clearSearch}>
            {t('empty.clear_search')}
          </button>
        {/snippet}
      </EmptyState>
    {/if}
    {#if browser.total !== null && browser.total > 0}
      <InfiniteSentinel
        count={browser.items.length}
        total={browser.total}
        loading={browser.loadingMore}
        hasMore={hasMore(browser.offset, browser.total)}
        skipFirst={browser.restoredFromSnapshot}
        onLoadMore={() => browser.loadMore()}
      />
    {/if}
  </section>
</div>

<style>
  .hero {
    padding: var(--space-12) 0 var(--space-8);
  }

  .hero h1 {
    font-size: var(--text-display);
    font-weight: 620;
    margin-bottom: var(--space-4);
  }

  .tagline {
    font-size: var(--text-lg);
    color: var(--ink-2);
    max-width: 46ch;
  }




  .section-title {
    font-size: var(--text-xl);
    margin: var(--space-8) 0 var(--space-4);
  }



  /* ── Demoted secondary teasers (Time Machine + Collections) ── */
  .secondary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--space-3);
    margin: var(--space-6) 0 var(--space-4);
  }

  .teaser {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-4) var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    text-decoration: none;
    color: inherit;
    transition: border-color 0.15s, transform 0.15s;
  }

  .teaser:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
  }

  .teaser-kicker {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
  }


  .teaser-cta {
    margin-top: var(--space-1);
    color: var(--accent);
    font-size: var(--text-sm);
  }

  .mw-teaser {
    cursor: default;
  }

  .mw-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-sm);
  }

  .mw-list li {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-2);
  }

  .mw-count {
    display: inline-flex;
    align-items: center;
    gap: 0.25em;
    color: var(--ink-3);
  }

  .error {
    padding: var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
  }
</style>
