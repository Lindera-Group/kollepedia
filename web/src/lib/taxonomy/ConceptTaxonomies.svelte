<script lang="ts">
  /** A concept's curated classifications (plan NG_TAXONOMIES):
   * - global categories as chips (the cross-collection search axis)
   * - the collection's own taxonomies (e.g. Parts) as structural metadata
   * Assignment lives on the CONCEPT — saving here never mints a version. */
  import {
    api,
    type ConceptOut,
    type ConceptTaxonomyOut,
    type TaxonomyOut
  } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { taxonomyValueName } from './valueName';

  interface Props {
    concept: ConceptOut;
    editable: boolean;
    onchanged: () => void;
  }

  let { concept, editable, onchanged }: Props = $props();

  const assigned = $derived(new Map(concept.taxonomies.map((tx) => [tx.taxonomy_id, tx])));

  let available = $state<TaxonomyOut[] | null>(null);
  let picks = $state<Record<string, string[]>>({});
  let saveState = $state<'idle' | 'saving' | 'error'>('idle');
  let error = $state<string | null>(null);
  let saved = $state(false);

  $effect(() => {
    if (!editable) return;
    api
      .taxonomies(concept.collection.slug)
      .then((all) => {
        available = all;
        picks = Object.fromEntries(
          all.map((tx) => [tx.id, assigned.get(tx.id)?.values.map((v) => v.id) ?? []])
        );
      })
      .catch((e) => (error = errorMessage(e)));
  });

  function toggle(taxonomy: TaxonomyOut, valueId: string): void {
    saved = false;
    const current = picks[taxonomy.id] ?? [];
    if (taxonomy.max_per_concept === 1) {
      picks = { ...picks, [taxonomy.id]: current.includes(valueId) ? [] : [valueId] };
      return;
    }
    picks = {
      ...picks,
      [taxonomy.id]: current.includes(valueId)
        ? current.filter((v) => v !== valueId)
        : [...current, valueId]
    };
  }

  async function save(): Promise<void> {
    if (saveState === 'saving' || !available) return;
    saveState = 'saving';
    error = null;
    saved = false;
    let anySaved = false;
    try {
      for (const tx of available) {
        await api.assignTaxonomyValues(concept.id, tx.id, picks[tx.id] ?? []);
        anySaved = true;
      }
      saveState = 'idle';
      saved = true;
    } catch (e) {
      saveState = 'error';
      error = errorMessage(e);
    } finally {
      // A mid-loop failure leaves earlier taxonomies written (each PUT is an
      // idempotent replace) — refetch so the UI never shows stale state.
      if (anySaved) onchanged();
    }
  }
</script>

<div class="ctax ui">
  {#if editable}
    <p class="curation-note">{t('tax.curation_note')}</p>
    {#if !available && !error}
      <p class="none" role="status">{t('tax.loading')}</p>
    {/if}
    {#each available ?? [] as tx (tx.id)}
      <fieldset>
        <legend>
          {tx.name}
          {#if tx.max_per_concept === 1}<span class="hint">{t('tax.pick_one')}</span>
          {:else if tx.min_per_concept > 0}<span class="hint">{t('tax.min_hint', { min: tx.min_per_concept })}</span>{/if}
        </legend>
        <div class="options" role="group">
          {#each tx.values as value (value.id)}
            <button
              type="button"
              class="cat-pill"
              aria-pressed={(picks[tx.id] ?? []).includes(value.id)}
              onclick={() => toggle(tx, value.id)}
              disabled={saveState === 'saving'}
            >
              {taxonomyValueName(value)}
            </button>
          {/each}
          {#if tx.values.length === 0}
            <span class="none">{t('tax.no_values')}</span>
          {/if}
        </div>
      </fieldset>
    {/each}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if saved}<p class="success" role="status"><Icon name="check" size={14} /> {t('tax.saved')}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-primary" onclick={save} disabled={saveState === 'saving'}>
        {saveState === 'saving' ? t('common.saving') : t('tax.save')}
      </button>
    </div>
  {/if}
</div>

<style>
  .curation-note {
    font-size: var(--text-xs);
    color: var(--ink-3);
    max-width: 60ch;
    margin: 0 0 var(--space-3);
  }

  fieldset {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-2) var(--space-3);
    margin: 0 0 var(--space-3);
  }

  legend {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  legend .hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  .options {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .none {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: var(--space-2) 0;
  }

  .success {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin: var(--space-2) 0;
  }

  .actions {
    display: flex;
    gap: var(--space-2);
  }
</style>
