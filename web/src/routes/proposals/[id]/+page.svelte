<script lang="ts">
  /** Proposal review view (Iteration 4) — diff of source head vs target head in
   * the Time Machine's word-diff language, version metadata for both sides,
   * a discussion thread and the decision row (merge/reject/withdraw).
   * Rights are enforced server-side; errors surface via ApiError.detail. */
  import { page } from '$app/state';
  import { night4, type ProposalOut } from '$lib/api';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import CommentThread from '$lib/discuss/CommentThread.svelte';
  import { errorMessage } from '$lib/errors';
  import DiffText from '$lib/proposals/DiffText.svelte';
  import StatusBadge from '$lib/proposals/StatusBadge.svelte';
  import { formatDate, statusLabel, t, type TranslationKey } from '$lib/i18n.svelte';
  import { shortId } from '$lib/proposals/cite';
  import { stripMarkdown } from '$lib/text';
  import { currentUser } from '$lib/user.svelte';

  const id = $derived(page.params.id ?? '');

  let proposal = $state<ProposalOut | null>(null);
  let error = $state<string | null>(null);

  let mode = $state<'before' | 'diff' | 'after'>('diff');
  let action = $state<'merge' | 'reject' | 'withdraw' | null>(null);
  let actionNote = $state('');
  let actionBusy = $state(false);
  let actionError = $state<string | null>(null);

  const modes = $derived<['before' | 'diff' | 'after', string][]>([
    ['before', t('sd.before')],
    ['diff', t('sd.changes')],
    ['after', t('sd.after')]
  ]);

  const canWrite = $derived(currentUser.handle !== '');
  const isAuthor = $derived(
    !!proposal?.created_by &&
      (proposal.created_by.handle === currentUser.handle || currentUser.is_super_admin)
  );

  const nameChanged = $derived(
    !!proposal?.source_head &&
      !!proposal.target_head &&
      proposal.source_head.canonical_form !== proposal.target_head.canonical_form
  );
  const defA = $derived(
    proposal?.target_head ? stripMarkdown(proposal.target_head.definition_md) : ''
  );
  const defB = $derived(
    proposal?.source_head ? stripMarkdown(proposal.source_head.definition_md) : ''
  );

  const RESOLVED_KEYS: Record<string, TranslationKey> = {
    merged: 'prop.resolved_merged',
    rejected: 'prop.resolved_rejected',
    withdrawn: 'prop.resolved_withdrawn'
  };

  async function load(proposalId: string, reset = true): Promise<void> {
    if (reset) proposal = null;
    error = null;
    try {
      proposal = await night4.proposal(proposalId);
    } catch (e) {
      error = errorMessage(e);
    }
  }

  $effect(() => {
    const proposalId = id;
    mode = 'diff';
    action = null;
    actionNote = '';
    actionError = null;
    load(proposalId);
  });

  function openAction(next: 'merge' | 'reject' | 'withdraw'): void {
    action = action === next ? null : next;
    actionNote = '';
    actionError = null;
  }

  async function runAction(): Promise<void> {
    if (!proposal || actionBusy || !action) return;
    if ((action === 'merge' || action === 'reject') && !actionNote.trim()) {
      actionError = t('prop.note_required');
      return;
    }
    actionBusy = true;
    actionError = null;
    try {
      if (action === 'merge') proposal = await night4.mergeProposal(proposal.id, actionNote.trim());
      else if (action === 'reject')
        proposal = await night4.rejectProposal(proposal.id, actionNote.trim());
      else proposal = await night4.withdrawProposal(proposal.id);
      action = null;
      actionNote = '';
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      actionBusy = false;
    }
  }
</script>

<svelte:head
  ><title>{proposal?.title ?? t('prop.fallback_title')} {t('typo.dash')} Kollepedia NG</title></svelte:head
>

<div class="container">
  <nav class="ui breadcrumb">
    <a href="/proposals">{t('prop.back')}</a>
  </nav>

  {#if error}
    <p class="err ui" role="alert">{t('prop.load_one_error', { error })}</p>
  {:else if !proposal}
    <p class="muted ui">{t('prop.loading_one')}</p>
  {:else}
    <article>
      <header class="head">
        <div class="title-row">
          <h1>{proposal.title}</h1>
          <StatusBadge status={proposal.status} />
        </div>
        <p class="meta ui">
          {t('prop.for_concept')}
          <a href="/concepts/{proposal.concept_id}">{proposal.canonical_form}</a>
          <span class="mono">{proposal.collection_slug}</span>
          <span class="mono">{proposal.source_branch_name} → {proposal.target_branch}</span>
        </p>
        <p class="meta ui">
          {t('prop.proposed_by')}
          {#if proposal.created_by}
            <a class="author" href="/authors/{proposal.created_by.handle}"
              ><strong>{proposal.created_by.display_name}</strong></a
            >
          {:else}
            <strong>{t('tm.unknown_author')}</strong>
          {/if}
          · {formatDate(proposal.created_at)}
        </p>
        {#if proposal.description}
          <p class="description">{proposal.description}</p>
        {/if}
      </header>

      {#if proposal.status !== 'open'}
        <div
          class="resolution ui"
          class:merged={proposal.status === 'merged'}
          class:rejected={proposal.status === 'rejected'}
          role="status"
        >
          <p class="res-line">
            <strong>{t(RESOLVED_KEYS[proposal.status] ?? 'prop.resolved_withdrawn')}</strong>
            {#if proposal.resolved_by || proposal.resolved_at}
              {t('prop.resolved_by_prefix')}
              <AuthorLink user={proposal.resolved_by} fallback={t('tm.unknown')} />,
              {proposal.resolved_at ? formatDate(proposal.resolved_at) : t('typo.dash')}
            {/if}
          </p>
          {#if proposal.resolution_note}
            <blockquote class="res-note">”{proposal.resolution_note}”</blockquote>
          {/if}
          {#if proposal.status === 'merged'}
            <p class="res-link">
              <a href="/concepts/{proposal.concept_id}/history"
                >{t('prop.view_merged_history')}</a
              >
            </p>
          {/if}
        </div>
      {/if}

      <section class="diff-section">
        <h2>{t('prop.diff_title')}</h2>
        {#if proposal.source_head && proposal.target_head}
          <div class="modes ui" role="radiogroup" aria-label={t('sd.aria')}>
            {#each modes as [value, label] (value)}
              <button
                class="btn"
                class:btn-primary={mode === value}
                role="radio"
                aria-checked={mode === value}
                onclick={() => (mode = value)}>{label}</button
              >
            {/each}
          </div>

          <h3 class="field-label diff-label ui">{t('edit.canonical_label')}</h3>
          <p class="name-diff">
            {#if nameChanged}
              <DiffText
                a={proposal.target_head.canonical_form}
                b={proposal.source_head.canonical_form}
                {mode}
              />
            {:else}
              {proposal.source_head.canonical_form}
              <span class="unchanged ui">{t('prop.unchanged')}</span>
            {/if}
          </p>

          <h3 class="field-label diff-label ui">{t('edit.definition_label')}</h3>
          <p class="def-diff">
            {#if defA === defB}
              {defB}
              <span class="unchanged ui">{t('prop.unchanged')}</span>
            {:else}
              <DiffText a={defA} b={defB} {mode} />
            {/if}
          </p>

          <div class="sides ui">
            <div class="side card">
              <p class="side-label">{t('prop.before_label')}</p>
              <p class="side-author">
                <strong><AuthorLink user={proposal.target_head.created_by} /></strong>
              </p>
              <p class="mono side-meta">
                {formatDate(proposal.target_head.created_at)} · {statusLabel(
                  proposal.target_head.status
                )} · {t('ver.meta_version', { id: shortId(proposal.target_head.id) })}
              </p>
              {#if proposal.target_head.note}
                <blockquote class="side-note">”{proposal.target_head.note}”</blockquote>
              {/if}
              <p class="mono side-link">
                <a href="/versions/{proposal.target_head.id}">{t('ver.permalink')}</a>
              </p>
            </div>
            <div class="side card">
              <p class="side-label">
                {t('prop.after_label', { branch: proposal.source_branch_name })}
              </p>
              <p class="side-author">
                <strong><AuthorLink user={proposal.source_head.created_by} /></strong>
              </p>
              <p class="mono side-meta">
                {formatDate(proposal.source_head.created_at)} · {statusLabel(
                  proposal.source_head.status
                )} · {t('ver.meta_version', { id: shortId(proposal.source_head.id) })}
              </p>
              {#if proposal.source_head.note}
                <blockquote class="side-note">”{proposal.source_head.note}”</blockquote>
              {/if}
              <p class="mono side-link">
                <a href="/versions/{proposal.source_head.id}">{t('ver.permalink')}</a>
              </p>
            </div>
          </div>
        {:else}
          <p class="muted ui">{t('prop.missing_versions')}</p>
        {/if}
      </section>

      {#if proposal.status === 'open'}
        <section class="decision ui">
          {#if canWrite}
            <div class="action-row">
              <button
                type="button"
                class="btn"
                aria-expanded={action === 'merge'}
                title={t('prop.merge_title')}
                disabled={actionBusy}
                onclick={() => openAction('merge')}>{t('prop.merge')}</button
              >
              <button
                type="button"
                class="btn"
                aria-expanded={action === 'reject'}
                title={t('prop.reject_title')}
                disabled={actionBusy}
                onclick={() => openAction('reject')}>{t('prop.reject')}</button
              >
              {#if isAuthor}
                <button
                  type="button"
                  class="btn btn-quiet"
                  aria-expanded={action === 'withdraw'}
                  disabled={actionBusy}
                  onclick={() => openAction('withdraw')}>{t('prop.withdraw')}</button
                >
              {/if}
            </div>

            {#if action === 'merge' || action === 'reject'}
              <div class="note-form">
                <label for="action-note"
                  >{t('edit.note_label')}
                  <span class="req">·&nbsp;{t('edit.note_required')}</span></label
                >
                <textarea
                  id="action-note"
                  class="input"
                  rows="2"
                  bind:value={actionNote}
                  disabled={actionBusy}
                  placeholder={action === 'merge'
                    ? t('prop.merge_note_placeholder')
                    : t('prop.reject_note_placeholder')}
                ></textarea>
                <div class="note-actions">
                  <button
                    type="button"
                    class="btn btn-primary"
                    disabled={actionBusy}
                    onclick={runAction}
                  >
                    {#if action === 'merge'}
                      {actionBusy ? t('prop.merging') : t('prop.merge')}
                    {:else}
                      {actionBusy ? t('prop.rejecting') : t('prop.reject')}
                    {/if}
                  </button>
                  <button
                    type="button"
                    class="btn btn-quiet"
                    disabled={actionBusy}
                    onclick={() => (action = null)}>{t('common.cancel')}</button
                  >
                </div>
              </div>
            {:else if action === 'withdraw'}
              <div class="note-form withdraw-confirm" role="alert">
                {t('prop.withdraw_q')}
                <button
                  type="button"
                  class="btn btn-quiet danger"
                  disabled={actionBusy}
                  onclick={runAction}
                >
                  {actionBusy ? t('prop.withdrawing') : t('common.yes')}
                </button>
                <button
                  type="button"
                  class="btn btn-quiet"
                  disabled={actionBusy}
                  onclick={() => (action = null)}>{t('common.cancel')}</button
                >
              </div>
            {/if}

            {#if actionError}
              <p class="err" role="alert">{t('prop.action_error', { error: actionError })}</p>
            {/if}
          {:else}
            <p class="muted">{t('prop.locked_hint')}</p>
          {/if}
        </section>
      {/if}

      <section class="discussion">
        <CommentThread kind="proposal" targetId={proposal.id} />
      </section>
    </article>
  {/if}
</div>

<style>

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .title-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .head h1 {
    margin-bottom: var(--space-2);
  }

  .head .meta {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin: 0 0 var(--space-2);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .head .meta .mono {
    color: var(--ink-3);
  }

  .author {
    color: inherit;
    text-decoration-color: color-mix(in srgb, var(--ink-3) 45%, transparent);
  }

  .author:hover {
    color: var(--accent);
  }

  .description {
    max-width: 65ch;
    white-space: pre-wrap;
    color: var(--ink-2);
    margin-top: var(--space-3);
  }

  .resolution {
    max-width: 65ch;
    margin: var(--space-4) 0 var(--space-6);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
  }

  .resolution.merged {
    border-color: var(--ins-strong);
    background: var(--ins-wash);
  }

  .resolution.rejected {
    border-color: var(--del-strong);
    background: var(--del-wash);
  }

  .res-line {
    margin: 0;
  }

  .res-note {
    margin: var(--space-2) 0 0;
    padding-left: var(--space-3);
    border-left: 3px solid var(--line);
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }

  .res-link {
    margin: var(--space-2) 0 0;
  }

  .diff-section {
    margin: var(--space-8) 0;
  }


  .modes {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
  }

  .diff-label {
    margin-top: var(--space-4);
  }

  .name-diff {
    font-family: var(--font-serif);
    font-size: var(--text-2xl);
    font-weight: 560;
    letter-spacing: -0.01em;
    margin: 0 0 var(--space-4);
  }

  .def-diff {
    font-size: var(--text-body-lg);
    line-height: 1.75;
    max-width: 65ch;
    white-space: pre-wrap;
    margin: 0 0 var(--space-6);
  }

  .unchanged {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .sides {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--space-4);
    max-width: 72ch;
  }

  .side {
    padding: var(--space-4);
    font-size: var(--text-sm);
  }

  .side-label {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: 0 0 var(--space-2);
  }

  .side-author {
    margin: 0 0 var(--space-1);
  }

  .side-meta {
    color: var(--ink-3);
    margin: 0 0 var(--space-2);
  }

  .side-note {
    margin: 0 0 var(--space-2);
    padding-left: var(--space-3);
    border-left: 3px solid var(--line);
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }

  .side-link {
    margin: 0;
  }

  .decision {
    max-width: 65ch;
    margin: var(--space-8) 0;
    padding: var(--space-4) var(--space-6);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
  }

  .action-row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .note-form {
    margin-top: var(--space-4);
  }

  .note-form label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .note-form .req {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  .note-form textarea {
    width: 100%;
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .note-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .withdraw-confirm {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .withdraw-confirm .danger {
    color: var(--del-strong);
  }

  .decision .err {
    margin: var(--space-3) 0 0;
  }

  .discussion {
    margin: var(--space-8) 0;
  }
</style>
