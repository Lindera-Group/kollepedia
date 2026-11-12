<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  /** Mest bevakade — watched concepts in popularity order. The backend
   * visibility-filters per session (org-private collections only for
   * members; anonymous sees public only). */
  import { night4, type MostWatchedItem } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';

  type ViewState =
    | { status: 'loading' }
    | { status: 'error'; message: string }
    | { status: 'ready'; items: MostWatchedItem[] };

  let view = $state<ViewState>({ status: 'loading' });

  $effect(() => {
    night4
      .mostWatched(50)
      .then((items) => (view = { status: 'ready', items }))
      .catch((e) => {
        view = { status: 'error', message: errorMessage(e) };
      });
  });
</script>

<svelte:head><title>{t('mw.head_title')}</title></svelte:head>

<div class="container">
  <nav class="ui breadcrumb"><a href="/">{t('common.back_to_search')}</a></nav>
  <PageHeader title={t('mw.h1')} intro={t('mw.intro')} />

  {#if view.status === 'loading'}
    <p class="muted ui">{t('mw.loading')}</p>
  {:else if view.status === 'error'}
    <p class="err ui" role="alert">{t('mw.load_error', { error: view.message })}</p>
  {:else if view.items.length === 0}
    <p class="muted ui">{t('mw.empty')}</p>
  {:else}
    <ol class="mw ui">
      {#each view.items as item, i (item.id)}
        <li>
          <span class="rank mono">{i + 1}</span>
          <span class="what">
            <a href="/concepts/{item.id}">{item.canonical_form}</a>
            <span class="coll mono">{item.collection.name}</span>
          </span>
          <span class="watchers" aria-label={t('mw.watchers_aria', { count: item.watcher_count })}>
            <Icon name="bell" size={13} />
            <span class="count-badge">{item.watcher_count}</span>
          </span>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .mw {
    list-style: none;
    margin: 0;
    padding: 0;
    max-width: 640px;
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    overflow: hidden;
    font-size: var(--text-sm);
  }

  .mw li {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-4);
    border-bottom: 1px solid var(--line);
  }

  .mw li:last-child {
    border-bottom: none;
  }

  .rank {
    flex: 0 0 1.6em;
    color: var(--ink-3);
    text-align: right;
  }

  .what {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
    min-width: 0;
  }

  .coll {
    color: var(--ink-3);
  }

  .watchers {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 0.3em;
    color: var(--ink-3);
    white-space: nowrap;
  }
</style>
