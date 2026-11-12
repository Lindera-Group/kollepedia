<script lang="ts">
  /** "Lägg till relation" — typed, note-bearing relations (VISION §4.4). */
  import { api, type ConceptListItem, type ConceptOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import ConceptCombobox from './ConceptCombobox.svelte';

  interface Props {
    concept: ConceptOut;
    oncreated: () => void;
  }

  let { concept, oncreated }: Props = $props();

  /** Matches RELATION_TYPES in server/app/models.py. */
  const RELATION_OPTIONS = $derived([
    { value: 'related_to', label: t('rel.type_related_to') },
    { value: 'broader', label: t('rel.type_broader') },
    { value: 'narrower', label: t('rel.type_narrower') },
    { value: 'exact_match', label: t('rel.type_exact_match') },
    { value: 'close_match', label: t('rel.type_close_match') },
    { value: 'supersedes', label: t('rel.type_supersedes') }
  ]);

  let open = $state(false);
  let relationType = $state('related_to');
  let target = $state<ConceptListItem | null>(null);
  let note = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const canWrite = $derived(currentUser.handle !== '');

  function reset(): void {
    relationType = 'related_to';
    target = null;
    note = '';
    error = null;
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    if (!target) {
      error = t('rel.error_no_target');
      return;
    }
    saving = true;
    try {
      await api.createRelation({
        relation_type: relationType,
        from_concept_id: concept.id,
        to_concept_id: target.id,
        note: note.trim() || undefined
      });
      reset();
      open = false;
      oncreated();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      saving = false;
    }
  }
</script>

<div class="relation-editor ui">
  {#if !open}
    <button
      class="btn btn-quiet opener"
      onclick={() => (open = true)}
      disabled={!canWrite}
      title={canWrite ? t('rel.add_title_can') : t('rel.add_title_locked')}
    >
      {t('rel.add')}
    </button>
    {#if !canWrite}
      <span class="locked-hint">{t('rel.locked_hint')}</span>
    {/if}
  {:else}
    <form class="panel" onsubmit={submit} aria-label={t('rel.form_aria')}>
      <div class="row">
        <div class="field">
          <label for="relation-type">{t('rel.type_label')}</label>
          <select id="relation-type" class="input" bind:value={relationType} disabled={saving}>
            {#each RELATION_OPTIONS as option (option.value)}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
        </div>

        <div class="field grow">
          <label for="relation-target">{t('rel.target_label')}</label>
          {#if target}
            <span class="pill target-pill">
              {target.canonical_form}
              <span class="mono coll">{target.collection_name}</span>
              <button
                type="button"
                class="remove"
                onclick={() => (target = null)}
                disabled={saving}
                aria-label={t('rel.remove_selected_aria', { name: target.canonical_form })}
              >×</button>
            </span>
          {:else}
            <ConceptCombobox
              inputId="relation-target"
              excludeId={concept.id}
              disabled={saving}
              onselect={(item) => (target = item)}
            />
          {/if}
        </div>
      </div>

      <div class="field">
        <label for="relation-note">{t('rel.note_label')} <span class="opt">{t('rel.note_opt')}</span></label>
        <input id="relation-note" class="input" type="text" bind:value={note} disabled={saving} />
      </div>

      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}

      <div class="actions">
        <button type="submit" class="btn btn-primary" disabled={saving}>
          {saving ? t('common.adding') : t('common.add')}
        </button>
        <button
          type="button"
          class="btn btn-quiet"
          disabled={saving}
          onclick={() => {
            reset();
            open = false;
          }}
        >
          {t('common.cancel')}
        </button>
      </div>
    </form>
  {/if}
</div>

<style>
  .relation-editor {
    margin-top: var(--space-3);
    max-width: 65ch;
  }

  .opener {
    color: var(--accent);
  }

  .locked-hint {
    margin-left: var(--space-2);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .panel {
    padding: var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
  }

  .row {
    display: flex;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .field {
    margin-bottom: var(--space-3);
  }

  .grow {
    flex: 1;
    min-width: 240px;
  }

  label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .opt {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  input[type='text'] {
    width: 100%;
  }

  select {
    width: auto;
    min-width: 190px;
  }

  .target-pill {
    gap: 0.5em;
    font-size: var(--text-sm);
    padding: 0.35em 0.9em;
  }

  .target-pill .coll {
    color: var(--ink-3);
  }

  .remove {
    border: none;
    background: none;
    padding: 0 0.1em;
    font-size: var(--text-sm);
    line-height: 1;
    color: var(--ink-3);
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .remove:hover {
    color: var(--del-strong);
  }

  .error {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--del-strong);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
  }
</style>
