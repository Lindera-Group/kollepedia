<script lang="ts">
  /** Title/description form for creating a change proposal from a branch.
   * Two modes: a branch picker (concept page) or a fixed branch (the
   * EditPanel follow-up right after a branch save). */
  import { night4, type BranchOut, type ProposalOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    conceptId: string;
    /** Picker mode: the concept's non-main branches. */
    branches?: BranchOut[];
    /** Fixed mode: the branch is already decided (no picker shown). */
    fixedBranch?: string;
    initialTitle?: string;
    oncreated: (proposal: ProposalOut) => void;
    oncancel: () => void;
    cancelLabel?: string;
  }

  let {
    conceptId,
    branches = [],
    fixedBranch,
    initialTitle = '',
    oncreated,
    oncancel,
    cancelLabel
  }: Props = $props();

  // Snapshot on mount by design: the parent mounts a fresh form per session.
  // svelte-ignore state_referenced_locally
  let branchName = $state(fixedBranch ?? branches[0]?.name ?? '');
  // svelte-ignore state_referenced_locally
  let title = $state(initialTitle);
  let description = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (saving) return;
    error = null;
    if (!branchName) {
      error = t('prop.error_no_branch');
      return;
    }
    if (!title.trim()) {
      error = t('prop.error_no_title');
      return;
    }
    saving = true;
    try {
      const proposal = await night4.createProposal(conceptId, {
        branch_name: branchName,
        title: title.trim(),
        ...(description.trim() ? { description: description.trim() } : {})
      });
      oncreated(proposal);
    } catch (e) {
      error = errorMessage(e);
    } finally {
      saving = false;
    }
  }
</script>

<form class="prop-form ui" onsubmit={submit} aria-label={t('prop.form_aria')}>
  {#if !fixedBranch}
    <div class="field">
      <label for="prop-branch">{t('prop.branch_label')}</label>
      <select id="prop-branch" class="input branch-select" bind:value={branchName} disabled={saving}>
        {#each branches as branch (branch.id)}
          <option value={branch.name}>{branch.name}</option>
        {/each}
      </select>
    </div>
  {/if}

  <div class="field">
    <label for="prop-title">{t('prop.title_label')}</label>
    <input
      id="prop-title"
      type="text"
      class="input"
      bind:value={title}
      disabled={saving}
      placeholder={t('prop.title_placeholder')}
    />
  </div>

  <div class="field">
    <label for="prop-description"
      >{t('prop.description_label')} <span class="opt">{t('common.optional_paren')}</span></label
    >
    <textarea
      id="prop-description"
      rows="3"
      class="input desc-input"
      bind:value={description}
      disabled={saving}
      placeholder={t('prop.description_placeholder')}
    ></textarea>
  </div>

  {#if error}
    <p class="err" role="alert">{error}</p>
  {/if}

  <div class="actions">
    <button type="submit" class="btn btn-primary" disabled={saving}>
      {saving ? t('prop.creating') : t('prop.create')}
    </button>
    <button type="button" class="btn btn-quiet" disabled={saving} onclick={oncancel}>
      {cancelLabel ?? t('common.cancel')}
    </button>
  </div>
</form>

<style>
  .prop-form {
    max-width: 65ch;
    padding: var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
  }

  .field {
    margin-bottom: var(--space-4);
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

  input[type='text'],
  textarea,
  select {
    width: 100%;
  }

  select {
    width: auto;
    min-width: 200px;
  }

  .branch-select {
    font-family: var(--font-mono);
  }

  .desc-input {
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .err {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-3);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
</style>
