<script lang="ts">
  /** Edit a historical or branch version from inside the history view.
   *
   * History is immutable — the form NEVER rewrites the base version; it
   * creates a new one at the chosen target (see editTargets.ts): the main
   * head (revise or promote-with-edits), the base's own branch head (revise),
   * or a brand-new branch forked from the base. A live diff (StaticDiff, the
   * same pipeline as the Time Machine's static mode) sits above the form so
   * the change being authored is always visible against the base version.
   *
   * Deliberately NO realtime collab and no 409 branch-and-reconcile here:
   * the base is a pinned historical version, so a concurrent main-head save
   * cannot invalidate it — promote/branch recompute lineage server-side. */
  import {
    api,
    type ConceptGraphOut,
    type VersionOut
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { VERSION_STATUSES } from '$lib/search/statuses';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import TagEditor from '$lib/edit/TagEditor.svelte';
  import DefinitionEditor from '$lib/editor/DefinitionEditor.svelte';
  import { formatDate, statusLabel, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import { editTargets, type EditTarget } from './editTargets';
  import { buildTransition } from './script';
  import StaticDiff from './StaticDiff.svelte';

  interface Props {
    graph: ConceptGraphOut;
    /** The pinned base — the historical/branch version being edited. */
    version: VersionOut;
    /** 1-based position on the current path, for "version X" labelling. */
    versionNumber: number;
    oncancel: () => void;
    /** Fires after a successful save; the owner refetches the graph. */
    onsaved: () => void;
  }

  let { graph, version, versionNumber, oncancel, onsaved }: Props = $props();

  const STATUSES = VERSION_STATUSES;

  // The base is deliberately frozen at mount (the owner mounts a fresh panel
  // per edit session) — the drafts must not follow a moving playhead.
  // svelte-ignore state_referenced_locally
  let canonicalForm = $state(version.canonical_form);
  // svelte-ignore state_referenced_locally
  let definitionMd = $state(version.definition_md);
  // svelte-ignore state_referenced_locally
  let status = $state(version.status === 'endorsed' ? 'proposed' : version.status);
  // svelte-ignore state_referenced_locally
  let tags = $state([...version.tags]);
  let note = $state('');

  const targets = $derived(editTargets(graph, version));
  let target = $state<EditTarget>('main');
  let branchName = $state('');

  let saveState = $state<'idle' | 'saving' | 'error'>('idle');
  let error = $state<string | null>(null);
  let noteError = $state<string | null>(null);

  const busy = $derived(saveState === 'saving');

  // The opener ("Redigera version X") unmounts when the panel opens — move
  // focus into the form so keyboard users are not dropped on <body>.
  let canonicalInput = $state<HTMLInputElement | undefined>();
  $effect(() => {
    canonicalInput?.focus();
  });

  /** Live diff: base → current draft, through the Time Machine's own diff
   * pipeline. The pseudo-version only needs the fields buildTransition reads. */
  const draftTransition = $derived(
    buildTransition(version, {
      ...version,
      canonical_form: canonicalForm,
      definition_md: definitionMd,
      status,
      tags
    })
  );

  const mainInfo = $derived(targets.find((i) => i.target === 'main'));
  const branchInfo = $derived(targets.find((i) => i.target === 'branch'));

  const targetExplanation = $derived.by((): string => {
    if (target === 'main') {
      return mainInfo?.baseIsMainHead
        ? t('he.explain_main_head')
        : t('he.explain_main', { x: String(versionNumber) });
    }
    if (target === 'branch') return t('he.explain_branch', { name: branchInfo?.branchName ?? '' });
    return t('he.explain_new_branch', { x: String(versionNumber) });
  });

  function defaultBranchName(): string {
    const handle = currentUser.handle || 'anonym';
    return `gren-av-${handle.toLowerCase().replace(/\s+/g, '-')}`;
  }

  function pickTarget(next: EditTarget): void {
    target = next;
    if (next === 'new-branch' && !branchName.trim()) branchName = defaultBranchName();
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    noteError = null;
    if (!canonicalForm.trim()) {
      error = t('edit.error_no_name');
      return;
    }
    if (!note.trim()) {
      noteError = t('edit.error_no_note');
      return;
    }
    if (target === 'new-branch' && !branchName.trim()) {
      error = t('edit.error_no_branch_name');
      return;
    }
    if (busy) return;
    saveState = 'saving';
    try {
      const content = {
        canonical_form: canonicalForm.trim(),
        definition_md: definitionMd,
        status,
        tags,
        note: note.trim()
      };
      if (target === 'main' && !mainInfo?.baseIsMainHead) {
        await api.promote(graph.concept_id, { version_id: version.id, ...content });
      } else if (target === 'new-branch') {
        await api.createVersion(graph.concept_id, {
          mode: 'branch',
          base_version_id: version.id,
          branch_name: branchName.trim(),
          language: version.language,
          ...content
        });
      } else {
        // 'main' with base = main head, or 'branch' with base = branch head.
        await api.createVersion(graph.concept_id, {
          mode: 'revise',
          base_version_id: version.id,
          language: version.language,
          ...content
        });
      }
      saveState = 'idle';
      onsaved();
    } catch (e) {
      saveState = 'error';
      error = errorMessage(e);
    }
  }
</script>

<section class="hedit card ui" aria-label={t('he.aria')}>
  <header class="head">
    <h2>{t('he.title', { x: String(versionNumber) })}</h2>
    <p class="base mono">
      <AuthorLink user={version.created_by} /> · {formatDate(version.created_at)}
      · {statusLabel(version.status)}
    </p>
  </header>

  <div class="livediff" aria-label={t('he.diff_aria', { x: String(versionNumber) })}>
    <p class="diff-heading">{t('he.diff_heading', { x: String(versionNumber) })}</p>
    <StaticDiff transition={draftTransition} />
  </div>

  <form onsubmit={submit} aria-label={t('he.title', { x: String(versionNumber) })}>
    <div class="field">
      <label for="he-canonical">{t('edit.canonical_label')}</label>
      <input
        id="he-canonical"
        type="text"
        class="input"
        bind:value={canonicalForm}
        bind:this={canonicalInput}
        disabled={busy}
        required
      />
    </div>

    <div class="field">
      <label for="he-definition">{t('edit.definition_label')}</label>
      <DefinitionEditor
        inputId="he-definition"
        value={definitionMd}
        onchange={(md) => (definitionMd = md)}
        disabled={busy}
      />
      <p class="hint">{t('edit.markdown_hint')}</p>
    </div>

    <div class="row">
      <div class="field grow">
        <label for="he-tags">{t('edit.tags_label')}</label>
        <TagEditor {tags} onchange={(next) => (tags = next)} disabled={busy} inputId="he-tags" />
      </div>
      <div class="field">
        <label for="he-status">{t('common.status')}</label>
        <select id="he-status" class="input" bind:value={status} disabled={busy}>
          {#each STATUSES as s (s)}
            <option value={s}>{statusLabel(s)}</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="field">
      <label for="he-note">
        {t('edit.note_label')} <span class="req" aria-hidden="true">·&nbsp;{t('edit.note_required')}</span>
      </label>
      <textarea
        id="he-note"
        rows="3"
        class="input"
        bind:value={note}
        disabled={busy}
        placeholder={t('edit.note_placeholder')}
        aria-describedby={noteError ? 'he-note-error' : undefined}
      ></textarea>
      {#if noteError}<p class="field-error" id="he-note-error" role="alert">{noteError}</p>{/if}
    </div>

    <fieldset class="targets">
      <legend>{t('he.target_label')}</legend>
      {#each targets as info (info.target)}
        <label class="target-option">
          <input
            type="radio"
            name="he-target"
            value={info.target}
            checked={target === info.target}
            onchange={() => pickTarget(info.target)}
            disabled={busy}
          />
          {#if info.target === 'main'}
            {t('he.target_main')}
          {:else if info.target === 'branch'}
            {t('he.target_branch', { name: info.branchName ?? '' })}
          {:else}
            {t('he.target_new_branch')}
          {/if}
        </label>
      {/each}
      <p class="explain" role="status">{targetExplanation}</p>
    </fieldset>

    {#if target === 'new-branch'}
      <div class="field branch-name">
        <label for="he-branch-name">{t('edit.branch_name_label')}</label>
        <input
          id="he-branch-name"
          type="text"
          class="input"
          bind:value={branchName}
          disabled={busy}
          autocomplete="off"
          spellcheck="false"
        />
      </div>
    {/if}

    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <div class="actions">
      <button type="submit" class="btn btn-primary" disabled={busy}>
        {busy ? t('common.saving') : t('common.save')}
      </button>
      <button type="button" class="btn btn-quiet" disabled={busy} onclick={oncancel}>
        {t('common.cancel')}
      </button>
    </div>
  </form>
</section>

<style>
  .hedit {
    margin-top: var(--space-6);
  }

  .head {
    margin-bottom: var(--space-4);
  }

  .head h2 {
    margin-bottom: var(--space-1);
  }

  .base {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0;
  }

  .livediff {
    border-block: 1px solid var(--line);
    margin-bottom: var(--space-6);
  }

  .diff-heading {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: var(--space-4) 0 0;
  }

  .field {
    margin-bottom: var(--space-4);
  }

  .row {
    display: flex;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .grow {
    flex: 1;
    min-width: 220px;
  }

  label,
  legend {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .req {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  input[type='text'],
  textarea,
  select {
    width: 100%;
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: var(--space-1) 0 0;
  }

  .targets {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    margin: 0 0 var(--space-4);
  }

  .target-option {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--ink);
    margin-bottom: var(--space-2);
    cursor: pointer;
  }

  .target-option input {
    accent-color: var(--accent);
  }

  .explain {
    font-size: var(--text-xs);
    color: var(--ink-2);
    margin: var(--space-2) 0 0;
    max-width: 60ch;
  }

  .field-error,
  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: var(--space-2) 0 0;
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }
</style>
