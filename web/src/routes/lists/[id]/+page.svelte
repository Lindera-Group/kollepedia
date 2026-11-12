<script lang="ts">
  import { page } from '$app/state';
  import Icon from '$lib/icons/Icon.svelte';
  import { EXPORT_FORMATS } from '$lib/exports/formats';
  import { api, type ListOut } from '$lib/api';
  import { compareUrl } from '$lib/compare/url';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { pinLabel } from '$lib/lists/pin';

  const id = $derived(page.params.id ?? '');

  let list = $state<ListOut | null>(null);
  let loadError = $state<string | null>(null);

  let confirmingId = $state<string | null>(null);
  let removingId = $state<string | null>(null);
  let removeError = $state<string | null>(null);

  $effect(() => {
    const listId = id;
    list = null;
    loadError = null;
    confirmingId = null;
    removeError = null;
    api
      .list(listId)
      .then((l) => (list = l))
      .catch((e) => (loadError = errorMessage(e)));
  });

  const items = $derived(list?.items ?? []);
  const conceptIds = $derived([...new Set(items.map((item) => item.concept_id))]);

  const exportFormats: [string, string][] = EXPORT_FORMATS.map((f) => [f.format, f.label]);

  async function removeItem(itemId: string): Promise<void> {
    if (!list) return;
    removingId = itemId;
    removeError = null;
    try {
      await api.deleteListItem(list.id, itemId);
      list = { ...list, items: list.items.filter((item) => item.id !== itemId) };
    } catch (e) {
      removeError = errorMessage(e);
    } finally {
      removingId = null;
      confirmingId = null;
    }
  }
</script>

<svelte:head><title>{list?.name ?? t('listd.fallback_title')} {t('typo.dash')} Kollepedia NG</title></svelte:head>

<div class="container">
  <nav class="ui breadcrumb">
    <a href="/lists">{t('listd.back')}</a>
  </nav>

  {#if loadError}
    <div class="card state-card ui">
      <p class="error" role="alert">{t('listd.load_error', { error: loadError })}</p>
    </div>
  {:else if !list}
    <p class="ui muted"><span class="spinner" aria-hidden="true"></span> {t('listd.loading')}</p>
  {:else}
    <header class="head">
      <h1>{list.name}</h1>
      {#if list.purpose}
        <p class="purpose">{list.purpose}</p>
      {/if}
      <p class="mono meta">{t('lists.meta', { count: items.length, date: formatDate(list.created_at) })}</p>
    </header>

    {#if items.length === 0}
      <div class="card state-card ui">
        <p>
          {t('listd.empty_1')} <strong>{t('list.add_button')}</strong> {t('listd.empty_2')}
          <a href="/">{t('listd.empty_link')}</a>.
        </p>
      </div>
    {:else}
      {#if conceptIds.length >= 2}
        <a class="compare-link" href={compareUrl(conceptIds)}>
          <span class="compare-icon" aria-hidden="true">⇄</span>
          <span>
            <strong>{t('listd.compare')}</strong>
            <span class="compare-sub ui">
              {t('listd.compare_sub', { count: conceptIds.length })}
            </span>
          </span>
        </a>
      {/if}

      {#if removeError}
        <p class="error ui" role="alert">{removeError}</p>
      {/if}

      <div class="table-scroll">
        <table class="ui">
          <thead>
            <tr>
              <th scope="col">{t('listd.th_concept')}</th>
              <th scope="col">{t('listd.th_version')}</th>
              <th scope="col">{t('listd.th_note')}</th>
              <th scope="col"><span class="sr-only">{t('listd.th_actions_sr')}</span></th>
            </tr>
          </thead>
          <tbody>
            {#each items as item (item.id)}
              <tr>
                <td class="term">
                  <a href="/concepts/{item.concept_id}">
                    {item.canonical_form ?? item.concept_id.slice(0, 8)}
                  </a>
                </td>
                <td class="pin mono">
                  {#if !item.follow_head && item.version_id}
                    <span class="pin-glyph" title={t('listd.pinned_title')} aria-hidden="true"><Icon name="pin" size={14} /></span>
                  {/if}
                  {pinLabel(item)}
                </td>
                <td class="note">{item.note ?? ''}</td>
                <td class="actions">
                  {#if confirmingId === item.id}
                    <span class="confirm">
                      {t('listd.remove_q')}
                      <button
                        class="btn btn-danger"
                        onclick={() => void removeItem(item.id)}
                        disabled={removingId === item.id}
                      >
                        {#if removingId === item.id}<span class="spinner" aria-hidden="true"
                          ></span>{:else}{t('listd.remove_yes')}{/if}
                      </button>
                      <button class="btn btn-quiet" onclick={() => (confirmingId = null)}>{t('common.cancel')}</button>
                    </span>
                  {:else}
                    <button
                      class="btn btn-quiet remove"
                      onclick={() => (confirmingId = item.id)}
                      aria-label={t('listd.remove_aria', { name: item.canonical_form ?? t('listd.the_concept') })}
                    >
                      {t('listd.remove')}
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <section class="export ui" aria-label={t('listd.export_aria')}>
        <h2>{t('listd.export_h2')}</h2>
        <p class="export-sub">
          {t('listd.export_sub')}
        </p>
        <div class="export-row">
          {#each exportFormats as [format, label] (format)}
            <a class="btn" href={api.exportUrl('lists', list.id, format)} download>{label}</a>
          {/each}
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>

  .head h1 {
    margin-bottom: var(--space-2);
  }

  .purpose {
    color: var(--ink-2);
    font-size: var(--text-lg);
    max-width: 60ch;
    margin-bottom: var(--space-2);
  }

  .meta {
    color: var(--ink-3);
    margin-bottom: var(--space-6);
  }

  .compare-link {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    max-width: 65ch;
    margin: 0 0 var(--space-6);
    padding: var(--space-4) var(--space-6);
    border: 1px solid var(--accent);
    border-radius: var(--radius-lg);
    background: var(--accent-soft);
    color: inherit;
    text-decoration: none;
    transition: transform 0.15s, box-shadow 0.15s;
  }

  .compare-link:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  .compare-icon {
    font-size: var(--text-xl);
    color: var(--accent);
  }

  .compare-sub {
    display: block;
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .table-scroll {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  th {
    text-align: left;
    font-weight: 600;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
  }

  td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--line);
    vertical-align: baseline;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .term a {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    font-weight: 560;
  }

  .pin {
    color: var(--ink-3);
    white-space: nowrap;
  }

  .pin-glyph {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    color: var(--accent);
  }

  .note {
    color: var(--ink-2);
    max-width: 32ch;
  }

  .actions {
    text-align: right;
    white-space: nowrap;
  }

  .confirm {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--del-strong);
  }

  .remove {
    color: var(--ink-3);
  }

  .remove:hover {
    color: var(--del-strong);
  }

  .export {
    margin-top: var(--space-8);
  }

  .export h2 {
    margin-bottom: var(--space-1);
  }

  .export-sub {
    color: var(--ink-3);
    font-size: var(--text-sm);
    max-width: 56ch;
  }

  .export-row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .export-row a {
    text-decoration: none;
  }

  .state-card {
    max-width: 560px;
  }

  .state-card p {
    margin: 0;
  }

  .muted {
    color: var(--ink-3);
  }

  .error {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-sm);
    background: var(--del-wash);
    margin-bottom: var(--space-4);
  }

  .spinner {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    border: 2px solid var(--line);
    border-top-color: var(--accent);
    border-radius: var(--radius-round);
    vertical-align: -0.1em;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
