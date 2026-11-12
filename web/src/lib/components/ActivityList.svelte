<script lang="ts">
  /** The ONE activity list — used by the concept page's Aktivitet subview and
   * by the history page, where it is two-way coupled to the player:
   * `highlightVersionId` marks rows, `onselect` seeks the player. Rows are
   * grouped by calendar DAY (never time of day — too high a resolution
   * against the timeline). Icons come from $lib/icons via activityIconName. */
  import type { ActivityItem } from '$lib/api';
  import { activityIconFilled, activityIconName, groupByDay } from '$lib/discuss/activity';
  import Icon from '$lib/icons/Icon.svelte';
  import { formatDate, t, type TranslationKey } from '$lib/i18n.svelte';

  let {
    items,
    highlightVersionId = null,
    onselect,
    compact = false
  }: {
    items: ActivityItem[];
    highlightVersionId?: string | null;
    onselect?: (item: ActivityItem) => void;
    compact?: boolean;
  } = $props();

  type FilterKey = 'versions' | 'endorsements' | 'branches' | 'merges' | 'proposals' | 'comments';

  const FILTER_OF: Record<ActivityItem['kind'], FilterKey> = {
    version: 'versions',
    endorsement: 'endorsements',
    branch: 'branches',
    merge: 'merges',
    proposal: 'proposals',
    proposal_merged: 'proposals',
    proposal_rejected: 'proposals',
    proposal_withdrawn: 'proposals',
    comment: 'comments'
  };

  const FILTERS: { key: FilterKey; label: TranslationKey; icon: 'edit' | 'star' | 'branch' | 'merge' | 'proposal' | 'talk' }[] = [
    { key: 'versions', label: 'hist.filter_versions', icon: 'edit' },
    { key: 'endorsements', label: 'hist.filter_endorsements', icon: 'star' },
    { key: 'branches', label: 'hist.filter_branches', icon: 'branch' },
    { key: 'merges', label: 'hist.filter_merges', icon: 'merge' },
    { key: 'proposals', label: 'hist.filter_proposals', icon: 'proposal' },
    { key: 'comments', label: 'hist.filter_comments', icon: 'talk' }
  ];

  const KIND_KEYS: Record<ActivityItem['kind'], TranslationKey> = {
    version: 'activity.kind_version',
    endorsement: 'activity.kind_endorsement',
    comment: 'activity.kind_comment',
    proposal: 'activity.kind_proposal',
    proposal_merged: 'activity.kind_proposal_merged',
    proposal_rejected: 'activity.kind_proposal_rejected',
    proposal_withdrawn: 'activity.kind_proposal_withdrawn',
    branch: 'activity.kind_branch',
    merge: 'activity.kind_merge'
  };

  let enabled = $state<Record<FilterKey, boolean>>({
    versions: true,
    endorsements: true,
    branches: true,
    merges: true,
    proposals: true,
    comments: true
  });

  const visible = $derived(items.filter((it) => enabled[FILTER_OF[it.kind] ?? 'versions']));
  const groups = $derived(groupByDay(visible));
</script>

<div class="actlist" class:compact>
  <div class="lhead ui" role="group" aria-label={t('hist.filter_aria')}>
    {#each FILTERS as f (f.key)}
      <button
        type="button"
        class="fchip"
        class:on={enabled[f.key]}
        class:off={!enabled[f.key]}
        aria-pressed={enabled[f.key]}
        onclick={() => (enabled = { ...enabled, [f.key]: !enabled[f.key] })}
      >
        <Icon name={f.icon} filled={f.icon === 'star'} size={12} />
        {t(f.label)}
      </button>
    {/each}
  </div>

  {#if groups.length === 0}
    <p class="empty ui">{t('hist.no_events')}</p>
  {:else}
    {#each groups as group (group.day)}
      <h3 class="adate mono">{formatDate(group.day)}</h3>
      {#each group.items as item, i (group.day + i)}
        <button
          type="button"
          class="arow ui"
          class:hl={item.version_id != null && item.version_id === highlightVersionId}
          onclick={() => onselect?.(item)}
        >
          <span class="ico" class:endorsed={item.kind === 'endorsement'} aria-hidden="true">
            <Icon name={activityIconName(item.kind)} filled={activityIconFilled(item.kind)} />
          </span>
          <span class="what">
            <span class="kind mono">{t(KIND_KEYS[item.kind] ?? 'activity.kind_version')}</span>
            {item.actor?.display_name ?? ''}
            {#if item.summary}{t('typo.dash')} {item.summary}{/if}
          </span>
        </button>
      {/each}
    {/each}
  {/if}
</div>

<style>
  .actlist {
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    overflow: hidden;
    font-size: var(--text-sm);
  }

  .lhead {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--line);
  }

  .fchip {
    display: inline-flex;
    align-items: center;
    gap: 0.3em;
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    padding: 0.15em 0.6em;
    background: var(--bg-raised);
    color: var(--ink-2);
    cursor: pointer;
    transition: border-color 0.15s, opacity 0.15s;
  }

  .fchip.on {
    border-color: var(--ink);
    color: var(--ink);
    font-weight: 600;
  }

  .fchip.off {
    opacity: 0.45;
    text-decoration: line-through;
  }

  .adate {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 400;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: 0;
    padding: var(--space-3) var(--space-4) var(--space-1);
    border-bottom: 1px solid var(--line);
    background: var(--bg);
  }

  .arow {
    display: flex;
    gap: var(--space-3);
    align-items: baseline;
    width: 100%;
    text-align: left;
    padding: var(--space-2) var(--space-4);
    border: none;
    border-bottom: 1px solid var(--line);
    background: transparent;
    color: var(--ink);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .arow:last-child {
    border-bottom: none;
  }

  .arow:hover {
    background: var(--bg-sunken);
  }

  .arow.hl {
    background: var(--accent-soft);
    box-shadow: inset 3px 0 0 var(--accent);
  }

  .ico {
    flex: 0 0 1.3rem;
    text-align: center;
    color: var(--accent);
  }

  .ico.endorsed {
    color: var(--endorsed);
  }

  .kind {
    color: var(--ink-3);
    margin-right: var(--space-1);
  }

  .empty {
    color: var(--ink-3);
    padding: var(--space-3) var(--space-4);
    margin: 0;
  }

  .compact .arow {
    padding: var(--space-1) var(--space-3);
  }

  .compact .lhead {
    padding: var(--space-2) var(--space-3);
  }
</style>
