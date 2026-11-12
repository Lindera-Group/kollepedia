<script lang="ts">
  import { goto } from '$app/navigation';
  import { EXPORT_FORMATS } from '$lib/exports/formats';
  import { api, type ListOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { formatDate, t } from '$lib/i18n.svelte';

  let lists = $state<ListOut[] | null>(null);
  let loadError = $state<string | null>(null);

  let formOpen = $state(false);
  let name = $state('');
  let purpose = $state('');
  let creating = $state(false);
  let createError = $state<string | null>(null);

  $effect(() => {
    void load();
  });

  async function load(): Promise<void> {
    loadError = null;
    try {
      lists = await api.lists();
    } catch (e) {
      loadError = errorMessage(e);
    }
  }

  async function createList(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!name.trim() || creating) return;
    creating = true;
    createError = null;
    try {
      const created = await api.createList({
        name: name.trim(),
        purpose: purpose.trim() || undefined
      });
      await goto(`/lists/${created.id}`);
    } catch (e) {
      createError = errorMessage(e);
    } finally {
      creating = false;
    }
  }

  function itemCount(list: ListOut): number {
    return (list.items ?? []).length;
  }
</script>

<svelte:head><title>{t('lists.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('lists.h1')}>
    {#snippet actions()}
      <button
        class="btn btn-primary ui"
        onclick={() => (formOpen = !formOpen)}
        aria-expanded={formOpen}
      >
        {formOpen ? t('common.close') : t('list.new_list')}
      </button>
    {/snippet}
    <p class="page-head-intro">
      {t('lists.tagline_1')} <em>{t('lists.tagline_em')}</em> {t('lists.tagline_2')}
    </p>
  </PageHeader>

  {#if formOpen}
    <form class="card new-form ui" onsubmit={createList}>
      <label class="field">
        <span>{t('common.name')}</span>
        <input class="input" type="text" bind:value={name} placeholder={t('list.name_placeholder')} required />
      </label>
      <label class="field">
        <span>{t('list.purpose_label')} <span class="muted">{t('common.optional_paren')}</span></span>
        <input class="input" type="text" bind:value={purpose} placeholder={t('list.purpose_placeholder')} />
      </label>
      {#if createError}
        <p class="error" role="alert">{createError}</p>
      {/if}
      <div class="row">
        <button class="btn btn-primary" type="submit" disabled={creating || !name.trim()}>
          {#if creating}<span class="spinner" aria-hidden="true"></span> {t('common.creating')}{:else}{t('lists.create_btn')}{/if}
        </button>
        <button class="btn btn-quiet" type="button" onclick={() => (formOpen = false)}>{t('common.cancel')}</button>
      </div>
    </form>
  {/if}

  {#if loadError}
    <div class="card state-card ui">
      <p class="error" role="alert">{t('lists.load_error', { error: loadError })}</p>
      <button class="btn" onclick={() => void load()}>{t('common.retry')}</button>
    </div>
  {:else if lists === null}
    <p class="ui muted"><span class="spinner" aria-hidden="true"></span> {t('list.loading_lists')}</p>
  {:else if lists.length === 0}
    <div class="card state-card ui">
      <p>
        {t('lists.empty_1')}
        <strong>{t('list.add_button')}</strong>.
      </p>
      {#if !formOpen}
        <button class="btn btn-primary" onclick={() => (formOpen = true)}>{t('list.new_list')}</button>
      {/if}
    </div>
  {:else}
    <div class="grid">
      {#each lists as list (list.id)}
        <div class="list-card">
          <a class="card-link" href="/lists/{list.id}"><h2>{list.name}</h2></a>
          {#if list.purpose}
            <p class="purpose">{list.purpose}</p>
          {/if}
          <p class="mono meta">{t('lists.meta', { count: itemCount(list), date: formatDate(list.created_at) })}</p>
          {#if itemCount(list) > 0}
            <p class="exports ui">
              <span class="mono">{t('coll.export_label')}</span>
              {#each EXPORT_FORMATS as { format, label } (format)}
                <a class="export-link" href={api.exportUrl('lists', list.id, format)} download
                  >{label}</a
                >
              {/each}
            </p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .new-form {
    max-width: 560px;
    margin-bottom: var(--space-8);
  }

  .field {
    display: block;
    margin-bottom: var(--space-3);
  }

  .field span {
    display: block;
    margin-bottom: var(--space-1);
    font-weight: 600;
    font-size: var(--text-sm);
  }

  .field input {
    width: 100%;
  }

  .muted {
    color: var(--ink-3);
    font-weight: 400;
  }

  .row {
    display: flex;
    gap: var(--space-2);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-4);
  }

  .list-card {
    display: block;
    padding: var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .list-card:hover {
    border-color: var(--ink);
    box-shadow: var(--shadow-sm);
  }

  .card-link {
    color: inherit;
    text-decoration: none;
  }

  .card-link:hover h2 {
    color: var(--accent);
  }

  .list-card h2 {
    font-size: var(--text-lg);
    margin-bottom: var(--space-1);
    transition: color 0.15s;
  }

  .exports {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin: var(--space-3) 0 0;
    font-size: var(--text-xs);
  }

  .exports .mono {
    color: var(--ink-3);
  }

  .export-link {
    color: var(--accent);
    text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent);
  }

  .purpose {
    color: var(--ink-2);
    font-size: var(--text-sm);
    margin-bottom: var(--space-2);
  }

  .meta {
    color: var(--ink-3);
    margin: 0;
  }

  .state-card {
    max-width: 560px;
  }

  .state-card p {
    margin-bottom: var(--space-3);
  }

  .error {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-sm);
    background: var(--del-wash);
    margin-bottom: var(--space-3);
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
