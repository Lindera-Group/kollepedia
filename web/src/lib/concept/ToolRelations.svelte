<script lang="ts">
  /** The Relationer tool subview (extracted 2026-07-12 per the concept-page
   * refactor memory): grouped relation list with inline two-step delete +
   * the relation editor. Concept-level — never versioned. */
  import { api, type ConceptOut } from '$lib/api';
  import RelationEditor from '$lib/edit/RelationEditor.svelte';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { groupRelations, relationLabel } from './relations';

  interface Props {
    concept: ConceptOut;
    /** Fires after a create/delete so the owner refetches the concept. */
    onchanged: () => void;
  }

  let { concept, onchanged }: Props = $props();

  let relationError = $state<string | null>(null);
  let confirmingRelationId = $state<string | null>(null);
  let deletingRelation = $state(false);

  const groupedRelations = $derived(groupRelations(concept.relations));

  async function deleteRelation(relationId: string): Promise<void> {
    deletingRelation = true;
    relationError = null;
    try {
      await api.deleteRelation(relationId);
      confirmingRelationId = null;
      onchanged();
    } catch (e) {
      relationError = errorMessage(e);
    } finally {
      deletingRelation = false;
    }
  }
</script>

<h3 class="subview-h ui">{t('concept.relations')}</h3>
<p class="subview-hint ui">{t('concept.concept_level_hint')}</p>
{#if relationError}
  <p class="rel-error ui" role="alert">
    {t('concept.relation_delete_failed', { error: relationError })}
  </p>
{/if}

{#each [...groupedRelations.entries()] as [type, relations] (type)}
  <div class="rel-group">
    <h3 class="rel-group-title ui">{relationLabel(type)}</h3>
    <ul>
      {#each relations as relation (relation.id)}
        <li>
          <a href="/concepts/{relation.other_concept_id}">{relation.other_canonical_form}</a>
          {#if relation.note}<span class="note ui">{t('typo.dash')} {relation.note}</span>{/if}
          {#if confirmingRelationId === relation.id}
            <span class="rel-confirm ui" role="alert">
              {t('concept.remove_relation_q')}
              <button
                class="btn btn-quiet danger"
                disabled={deletingRelation}
                onclick={() => deleteRelation(relation.id)}
              >
                {deletingRelation ? t('concept.removing') : t('common.yes')}
              </button>
              <button
                class="btn btn-quiet"
                disabled={deletingRelation}
                onclick={() => {
                  confirmingRelationId = null;
                  relationError = null;
                }}
              >
                {t('common.cancel')}
              </button>
            </span>
          {:else}
            <button
              class="rel-remove ui"
              onclick={() => {
                confirmingRelationId = relation.id;
                relationError = null;
              }}
              aria-label={t('concept.remove_relation_aria', {
                name: relation.other_canonical_form
              })}
              title={t('concept.remove_relation_title')}>×</button
            >
          {/if}
        </li>
      {/each}
    </ul>
  </div>
{/each}

<RelationEditor {concept} oncreated={onchanged} />

<style>
  .rel-error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin-bottom: var(--space-3);
  }

  .rel-group {
    margin-bottom: var(--space-4);
  }

  .rel-group-title {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .rel-group ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .rel-group li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    font-size: var(--text-sm);
  }

  .note {
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .rel-confirm {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
  }

  .danger {
    color: var(--del-strong);
  }

  .rel-remove {
    border: none;
    background: none;
    color: var(--ink-3);
    font-size: var(--text-sm);
    cursor: pointer;
    padding: 0 var(--space-1);
    border-radius: var(--radius-sm);
  }

  .rel-remove:hover {
    color: var(--del-strong);
  }
</style>
