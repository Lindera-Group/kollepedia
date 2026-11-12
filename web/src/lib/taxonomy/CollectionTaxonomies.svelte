<script lang="ts">
  /** Curation of a COLLECTION's own taxonomies (plan NG_TAXONOMIES follow-up):
   * shown to collection managers on the collection page. Global categories
   * are curated on /admin/taxonomies — this panel handles the collection's
   * structural vocabularies (e.g. the source standard's Parts, min=max=1). */
  import { api, type CollectionOut, type TaxonomyOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { taxonomyValueName } from './valueName';

  interface Props {
    collection: CollectionOut;
  }

  let { collection }: Props = $props();

  let taxonomies = $state<TaxonomyOut[] | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let draft = $state<Record<string, string>>({});
  let confirmingId = $state<string | null>(null);

  async function load(): Promise<void> {
    error = null;
    try {
      const all = await api.taxonomies(collection.slug);
      taxonomies = all.filter((tx) => tx.scope === 'collection');
    } catch (e) {
      error = errorMessage(e);
    }
  }

  $effect(() => {
    void load();
  });

  async function createParts(): Promise<void> {
    if (busy) return;
    busy = true;
    error = null;
    try {
      await api.createTaxonomy({
        slug: 'parts',
        name: t('tax.parts_name'),
        description: t('tax.parts_desc'),
        scope: 'collection',
        collection_id: collection.id,
        min_per_concept: 1,
        max_per_concept: 1
      });
      await load();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      busy = false;
    }
  }

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

<section class="ctx card ui" aria-label={t('tax.coll_h2')}>
  <h2>{t('tax.coll_h2')}</h2>
  <p class="hint">{t('tax.coll_hint')}</p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#each taxonomies ?? [] as tx (tx.id)}
    <div class="tax">
      <h3>
        {tx.name}
        {#if tx.max_per_concept === 1}<span class="mono meta">{t('tax.pick_one')}</span>{/if}
      </h3>
      <ul class="values">
        {#each tx.values as value (value.id)}
          <li>
            <span class="cat-pill">{taxonomyValueName(value)}</span>
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
        {#if tx.values.length === 0}
          <li class="none">{t('tax.no_values')}</li>
        {/if}
      </ul>
      <form class="add" onsubmit={(e) => { e.preventDefault(); void addValue(tx.id); }}>
        <label class="sr-only" for="ctx-add-{tx.id}">{t('taxadmin.add_label')}</label>
        <input
          id="ctx-add-{tx.id}"
          class="input"
          type="text"
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
    </div>
  {/each}

  {#if taxonomies !== null && !taxonomies.some((tx) => tx.slug === 'parts')}
    <button type="button" class="btn" onclick={createParts} disabled={busy}>
      {t('tax.create_parts')}
    </button>
  {/if}
</section>

<style>
  .ctx {
    margin-top: var(--space-6);
  }

  .ctx h2 {
    margin-bottom: var(--space-2);
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    max-width: 60ch;
    margin: 0 0 var(--space-3);
  }

  .tax {
    margin-bottom: var(--space-4);
  }

  .tax h3 {
    font-size: var(--text-sm);
    margin-bottom: var(--space-1);
  }

  .meta {
    font-size: var(--text-xs);
    color: var(--ink-3);
    font-weight: 400;
  }

  .values {
    list-style: none;
    margin: 0 0 var(--space-2);
    padding: 0;
  }

  .values {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .values li {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-sm);
  }

  .none {
    color: var(--ink-3);
    font-size: var(--text-xs);
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
  }

  .add input {
    flex: 1;
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-2);
  }
</style>
