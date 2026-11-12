<script lang="ts">
  /** Change-proposal queue (Iteration 4) — PRs for begrepp, filtered by status
   * and collection. The backend is being built in parallel; errors surface
   * gracefully via ApiError.detail. */
  import { api, night4, type CollectionOut, type ProposalOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import StatusBadge from '$lib/proposals/StatusBadge.svelte';
  import { formatDate, t } from '$lib/i18n.svelte';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  type StatusFilter = 'open' | 'merged' | 'rejected' | 'all';

  let statusFilter = $state<StatusFilter>('open');
  let collectionFilter = $state('');
  let proposals = $state<ProposalOut[] | null>(null);
  let error = $state<string | null>(null);
  let collections = $state<CollectionOut[]>([]);

  const FILTERS = $derived<[StatusFilter, string][]>([
    ['open', t('prop.filter_open')],
    ['merged', t('prop.filter_merged')],
    ['rejected', t('prop.filter_rejected')],
    ['all', t('prop.filter_all')]
  ]);

  $effect(() => {
    api
      .collections()
      .then((list) => (collections = list))
      .catch(() => {
        /* the collection filter simply stays empty */
      });
  });

  $effect(() => {
    const status = statusFilter;
    const collection = collectionFilter;
    proposals = null;
    error = null;
    night4
      .proposals({
        ...(status !== 'all' ? { status } : {}),
        ...(collection ? { collection } : {})
      })
      .then((list) => (proposals = list))
      .catch((e) => {
        proposals = [];
        error = errorMessage(e);
      });
  });
</script>

<svelte:head><title>{t('prop.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('prop.h1')} intro={t('prop.intro')} />

  <div class="controls ui">
    <div class="filters" role="group" aria-label={t('prop.filter_aria')}>
      {#each FILTERS as [value, label] (value)}
        <button
          type="button"
          class="filter-chip"
          aria-pressed={statusFilter === value}
          onclick={() => (statusFilter = value)}
        >
          {label}
        </button>
      {/each}
    </div>
    <select
      class="coll-filter"
      bind:value={collectionFilter}
      aria-label={t('prop.collection_filter_aria')}
    >
      <option value="">{t('prop.all_collections')}</option>
      {#each collections as collection (collection.id)}
        <option value={collection.slug}>{collection.name}</option>
      {/each}
    </select>
  </div>

  {#if proposals === null}
    <p class="muted ui">{t('prop.loading')}</p>
  {:else if error}
    <p class="err ui" role="alert">{t('prop.load_error', { error })}</p>
  {:else if proposals.length === 0}
    <p class="muted ui">
      {statusFilter === 'open' && !collectionFilter
        ? t('prop.empty_open')
        : t('prop.empty_filtered')}
    </p>
  {:else}
    <ul class="cards">
      {#each proposals as proposal (proposal.id)}
        <li>
          <article class="card prop-card">
            <div class="card-head">
              <h2><a href="/proposals/{proposal.id}">{proposal.title}</a></h2>
              <StatusBadge status={proposal.status} />
            </div>
            <p class="concept ui">
              <a href="/concepts/{proposal.concept_id}">{proposal.canonical_form}</a>
              <span class="mono coll">{proposal.collection_slug}</span>
              <span class="mono flow"
                >{proposal.source_branch_name} → {proposal.target_branch}</span
              >
            </p>
            <p class="meta mono">
              <AuthorLink user={proposal.created_by} /> · {formatDate(proposal.created_at)}
            </p>
          </article>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
    margin: var(--space-6) 0 var(--space-4);
  }

  .filters {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }

  .coll-filter {
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    color: var(--ink);
    max-width: 280px;
  }

  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .cards {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    max-width: 72ch;
  }

  .prop-card {
    padding: var(--space-4) var(--space-6);
  }

  .card-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .card-head h2 {
    font-size: var(--text-lg);
    margin: 0;
  }

  .card-head h2 a {
    color: inherit;
    text-decoration-color: color-mix(in srgb, var(--ink-3) 45%, transparent);
  }

  .card-head h2 a:hover {
    color: var(--accent);
  }

  .concept {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin: var(--space-2) 0;
    font-size: var(--text-sm);
  }

  .concept .coll,
  .concept .flow {
    color: var(--ink-3);
  }

  .meta {
    margin: 0;
    color: var(--ink-3);
  }
</style>
