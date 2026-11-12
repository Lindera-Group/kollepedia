<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import { listAuthors, type AuthorOut } from '$lib/api';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let q = $state('');
  // Writable derived: renders the load seed (SSR included); search results
  // assign an override, and navigations reset it to fresh data. A null seed
  // means the SSR load failed — rendered as a soft state below (paket D).
  let authors = $derived<AuthorOut[]>(data.authors ?? []);
  let loading = $state(false);
  let error = $state<string | null>(null);

  let timer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const query = q.trim();
    const seeded = data.authors; // tracked: re-runs on client navigations
    clearTimeout(timer);
    // The unfiltered directory is seeded by the load function; only searches
    // fetch client-side.
    if (!query) {
      authors = seeded ?? [];
      loading = false;
      error = null;
      return;
    }
    timer = setTimeout(async () => {
      loading = true;
      error = null;
      try {
        authors = await listAuthors(query, 200);
      } catch (e) {
        error = errorMessage(e);
      } finally {
        loading = false;
      }
    }, 220);
    return () => clearTimeout(timer);
  });

  function counts(author: AuthorOut): string {
    const parts: string[] = [`${author.concept_count} ${t('common.concepts')}`];
    if (author.section_count > 0) {
      parts.push(
        `${author.section_count} ${author.section_count === 1 ? t('authors.section_singular') : t('authors.sections')}`
      );
    }
    if (author.version_count > 0) {
      parts.push(
        `${author.version_count} ${author.version_count === 1 ? t('common.version_singular') : t('common.versions')}`
      );
    }
    return parts.join(' · ');
  }
</script>

<svelte:head>
  <title>{t('authors.head_title')}</title>
  <meta name="description" content={t('authors.tagline')} />
</svelte:head>

<div class="container">
  <PageHeader title={t('authors.h1')} intro={t('authors.tagline')} />

  <div class="search ui">
    <input
      type="search"
      class="input author-search"
      placeholder={t('authors.search_placeholder')}
      bind:value={q}
      aria-label={t('authors.search_aria')}
    />
  </div>

  {#if error}
    <p class="error ui" role="alert">{t('authors.load_error', { error })}</p>
  {:else if loading}
    <p class="ui muted">{t('authors.loading')}</p>
  {:else if data.authors === null && !q.trim()}
    <EmptyState icon="person" heading={t('authd.loaderr_h')} body={t('authd.loaderr_body')}>
      {#snippet actions()}
        <button type="button" class="btn" onclick={() => invalidateAll()}>
          {t('empty.try_again')}
        </button>
      {/snippet}
    </EmptyState>
  {:else if authors.length === 0}
    {#if q.trim()}
      <EmptyState icon="search" heading={t('authors.no_match', { query: q.trim() })}>
        {#snippet actions()}
          <button type="button" class="btn" onclick={() => (q = '')}>
            {t('empty.clear_search')}
          </button>
        {/snippet}
      </EmptyState>
    {:else}
      <EmptyState icon="person" heading={t('authors.none')} />
    {/if}
  {:else}
    <p class="ui muted count" role="status">{t('authors.count', { count: authors.length })}</p>
    <div class="grid">
      {#each authors as author (author.id)}
        <a class="author-card card" href="/authors/{author.handle}">
          <div class="card-top">
            <h2>{author.display_name}</h2>
            {#if author.activated}
              <span class="pill st-activated ui" title={t('authors.activated_title')}
                >{t('authors.activated')}</span
              >
            {:else}
              <span class="pill st-historic ui" title={t('authors.historic_title')}
                >{t('authors.historic')}</span
              >
            {/if}
          </div>
          {#if author.affiliation}
            <p class="affiliation">{author.affiliation}</p>
          {/if}
          <p class="mono stats">{counts(author)}</p>
          {#if author.collections.length}
            <p class="pills ui">
              {#each author.collections as coll (coll.slug)}
                <span class="pill">{coll.name}</span>
              {/each}
            </p>
          {/if}
        </a>
      {/each}
    </div>
  {/if}
</div>

<style>
  .search {
    margin: var(--space-6) 0 var(--space-8);
    max-width: 560px;
  }

  /* The big serif directory search — a deliberate flavour of .input. */
  .author-search {
    width: 100%;
    font-size: var(--text-lg);
    font-family: var(--font-serif);
    padding: var(--space-3) var(--space-4);
    border-color: var(--line-strong);
    border-radius: var(--radius-lg);
  }

  .author-search:focus {
    outline: 2px solid var(--focus);
    outline-offset: 1px;
  }

  .count {
    margin-bottom: var(--space-4);
  }

  .muted {
    color: var(--ink-3);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--space-4);
  }

  .author-card {
    display: block;
    text-decoration: none;
    color: inherit;
    transition:
      border-color 0.15s,
      transform 0.15s;
  }

  .author-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
  }

  .card-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .author-card h2 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-1);
  }

  .st-activated {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .st-historic {
    border-style: dashed;
    border-color: var(--line-strong);
    color: var(--ink-3);
  }

  .affiliation {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-2);
  }

  .stats {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0 0 var(--space-2);
  }

  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: 0;
  }

  .error {
    padding: var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
  }
</style>
