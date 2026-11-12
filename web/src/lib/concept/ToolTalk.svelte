<script lang="ts">
  /** The Diskussion tool subview (extracted 2026-07-12): filter chips,
   * proposal cards + propose-from-branch flow, and the comment thread. */
  import type { BranchOut, ConceptOut, ProposalOut } from '$lib/api';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import CommentThread from '$lib/discuss/CommentThread.svelte';
  import { formatDate, t } from '$lib/i18n.svelte';
  import ProposalForm from '$lib/proposals/ProposalForm.svelte';
  import StatusBadge from '$lib/proposals/StatusBadge.svelte';

  interface Props {
    concept: ConceptOut;
    proposals: ProposalOut[];
    proposalsError: string | null;
    nonMainBranches: BranchOut[];
    canWrite: boolean;
    /** Fires after a proposal was created so the owner refetches the list. */
    onproposed: () => void;
  }

  let { concept, proposals, proposalsError, nonMainBranches, canWrite, onproposed }: Props =
    $props();

  let discFilter = $state<'all' | 'proposals' | 'comments'>('all');
  let proposing = $state(false);
  let proposalCreated = $state<ProposalOut | null>(null);
</script>

<h3 class="subview-h ui">{t('disc.title')}</h3>
<div class="fchip-row ui" role="group" aria-label={t('cpage.tools_aria')}>
  <button
    type="button"
    class="filter-chip"
    aria-pressed={discFilter === 'all'}
    onclick={() => (discFilter = 'all')}
  >
    {t('cpage.disc_filter_all')}
  </button>
  <button
    type="button"
    class="filter-chip"
    aria-pressed={discFilter === 'proposals'}
    onclick={() => (discFilter = 'proposals')}
  >
    {t('cpage.disc_filter_proposals')}
  </button>
  <button
    type="button"
    class="filter-chip"
    aria-pressed={discFilter === 'comments'}
    onclick={() => (discFilter = 'comments')}
  >
    {t('cpage.disc_filter_comments')}
  </button>
</div>

{#if discFilter !== 'comments'}
  <div class="prop-cards">
    {#if proposalsError}
      <p class="err ui" role="alert">{t('prop.load_error', { error: proposalsError })}</p>
    {:else if proposals.length === 0}
      <p class="muted ui">{t('cpage.disc_no_proposals')}</p>
    {:else}
      {#each proposals as proposal (proposal.id)}
        <div class="prop-card">
          <div class="prop-card-head">
            <StatusBadge status={proposal.status} />
            <a href="/proposals/{proposal.id}">{proposal.title}</a>
          </div>
          <p class="prop-card-meta mono">
            {proposal.source_branch_name} → {proposal.target_branch} ·
            <AuthorLink user={proposal.created_by} /> ·
            {formatDate(proposal.created_at)}
          </p>
          <a class="prop-card-link ui" href="/proposals/{proposal.id}">{t('prop.created_link')}</a>
        </div>
      {/each}
    {/if}

    {#if proposalCreated}
      <p class="link-confirm ui" role="status">
        <Icon name="check" size={14} /> {t('prop.created')} {t('typo.dash')}
        <a href="/proposals/{proposalCreated.id}">{t('prop.created_link')}</a>
      </p>
    {/if}

    {#if canWrite && nonMainBranches.length}
      {#if !proposing}
        <button
          type="button"
          class="btn link-btn ui"
          title={t('prop.propose_title')}
          onclick={() => {
            proposing = true;
            proposalCreated = null;
          }}
        >
          {t('prop.propose_from_branch')}
        </button>
      {:else}
        <ProposalForm
          conceptId={concept.id}
          branches={nonMainBranches}
          oncreated={(proposal) => {
            proposing = false;
            proposalCreated = proposal;
            onproposed();
          }}
          oncancel={() => (proposing = false)}
        />
      {/if}
    {/if}
  </div>
{/if}

{#if discFilter !== 'proposals'}
  <CommentThread kind="concept" targetId={concept.id} />
{/if}

<style>
  .fchip-row {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
  }

  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .prop-cards {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .prop-card {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    background: var(--bg);
  }

  .prop-card-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-1);
    font-size: var(--text-sm);
  }

  .prop-card-meta {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0 0 var(--space-1);
  }

  .prop-card-link {
    font-size: var(--text-xs);
  }

  .link-confirm {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
  }

  .link-btn {
    align-self: flex-start;
  }
</style>
