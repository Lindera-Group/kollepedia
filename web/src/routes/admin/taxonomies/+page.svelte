<script lang="ts">
  /** Super-admin curation of the GLOBAL taxonomies (plan NG_TAXONOMIES).
   * The vocabulary is deliberately mutable: it follows the corpus to keep
   * global search simple. Collection taxonomies are curated via API (their
   * UI lives with the collection — follow-up in the plan). */
  import { api, type TaxonomyOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  let taxonomies = $state<TaxonomyOut[] | null>(null);
  let error = $state<string | null>(null);
  let draft = $state<Record<string, string>>({});
  let busy = $state(false);

  const isSuper = $derived(currentUser.is_super_admin);

  async function load(): Promise<void> {
    error = null;
    try {
      taxonomies = await api.taxonomies();
    } catch (e) {
      error = errorMessage(e);
    }
  }

  $effect(() => {
    if (isSuper) void load();
  });

  async function addValue(taxonomyId: string): Promise<void> {
    const name = (draft[taxonomyId] ?? '').trim();
    if (!name || busy) return;
    busy = true;
    error = null;
    try {
      await api.createTaxonomyValue(taxonomyId, name);
      draft = { ...draft, [taxonomyId]: '' };
      await load();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      busy = false;
    }
  }

  // Inline two-step confirm (guardrails §10) — deletion also removes the
  // value from every concept carrying it.
  let confirmingId = $state<string | null>(null);

  async function removeValue(valueId: string): Promise<void> {
    if (busy) return;
    busy = true;
    error = null;
    try {
      await api.deleteTaxonomyValue(valueId);
      confirmingId = null;
      await load();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>{t('taxadmin.head_title')}</title></svelte:head>

<div class="container narrow">
  <nav class="ui breadcrumb"><a href="/admin">{t('admin.back_to_hub')}</a></nav>
  <PageHeader title={t('taxadmin.h1')} />

  {#if !isSuper}
    <p class="ui" role="status">{t('taxadmin.guard')}</p>
  {:else}
    <p class="intro">{t('tax.curation_note')}</p>
    {#if error}<p class="error ui" role="alert">{error}</p>{/if}
    {#each taxonomies ?? [] as tx (tx.id)}
      <section class="card ui block">
        <h2>{tx.name} <span class="mono slug">{tx.slug}</span></h2>
        {#if tx.description}<p class="desc">{tx.description}</p>{/if}
        <ul class="values">
          {#each tx.values as value (value.id)}
            <li>
              <span>{value.name}</span>
              {#if confirmingId === value.id}
                <span class="confirm" role="alert">
                  {t('taxadmin.delete_confirm')}
                  <button type="button" class="btn btn-danger" disabled={busy} onclick={() => removeValue(value.id)}>{t('common.yes')}</button>
                  <button type="button" class="btn btn-quiet" onclick={() => (confirmingId = null)}>{t('common.cancel')}</button>
                </span>
              {:else}
                <button
                  type="button"
                  class="btn btn-quiet del"
                  onclick={() => (confirmingId = value.id)}
                  aria-label={t('taxadmin.delete_aria', { name: value.name })}
                >×</button>
              {/if}
            </li>
          {/each}
        </ul>
        <form class="add" onsubmit={(e) => { e.preventDefault(); void addValue(tx.id); }}>
          <label class="sr-only" for="add-{tx.id}">{t('taxadmin.add_label')}</label>
          <input
            id="add-{tx.id}"
            type="text"
            class="input"
            bind:value={
              () => draft[tx.id] ?? '',
              (v) => (draft = { ...draft, [tx.id]: v })
            }
            placeholder={t('taxadmin.add_placeholder')}
            disabled={busy}
          />
          <button type="submit" class="btn" disabled={busy || !(draft[tx.id] ?? '').trim()}>
            {t('common.add')}
          </button>
        </form>
      </section>
    {/each}
  {/if}
</div>

<style>
  .intro {
    max-width: 60ch;
    color: var(--ink-2);
    margin-bottom: var(--space-6);
  }

  .block {
    margin-bottom: var(--space-6);
  }

  .slug {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .desc {
    font-size: var(--text-sm);
    color: var(--ink-2);
    max-width: 60ch;
  }

  .values {
    list-style: none;
    margin: var(--space-3) 0;
    padding: 0;
  }

  .values li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--line);
    font-size: var(--text-sm);
  }

  .del {
    color: var(--ink-3);
    padding: 0 var(--space-2);
  }

  .del:hover {
    color: var(--del-strong);
  }

  .confirm {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
  }

  .add {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .add input {
    flex: 1;
  }
</style>
