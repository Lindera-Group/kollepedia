<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  /** Activity feed (Iteration 4) — events across watched concepts, grouped by
   * day. Computed server-side; requires an identity. */
  import { markSeen } from '$lib/activityBell.svelte';
  import { night4, type ActivityItem } from '$lib/api';
  import { activityIconFilled, activityIconName, groupByDay } from '$lib/discuss/activity';
  import { errorMessage } from '$lib/errors';
  import Icon from '$lib/icons/Icon.svelte';
  import { formatDate, t, type TranslationKey } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';

  let items = $state<ActivityItem[] | null>(null);
  let error = $state<string | null>(null);

  const canRead = $derived(currentUser.handle !== '');
  const groups = $derived(groupByDay(items ?? []));

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

  $effect(() => {
    if (!canRead) {
      items = null;
      error = null;
      return;
    }
    items = null;
    error = null;
    night4
      .myActivity(50)
      .then((list) => {
        items = list;
        // Visiting the feed marks everything as seen — the header bell
        // goes back to its quiet outline state.
        void markSeen();
      })
      .catch((e) => {
        items = [];
        error = errorMessage(e);
      });
  });
</script>

<svelte:head><title>{t('activity.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('activity.h1')} intro={t('activity.intro')} />

  {#if !canRead}
    <p class="muted ui">{t('activity.locked')}</p>
  {:else if items === null}
    <p class="muted ui">{t('activity.loading')}</p>
  {:else if error}
    <p class="err ui" role="alert">{t('activity.load_error', { error })}</p>
  {:else if items.length === 0}
    <p class="muted ui empty">{t('activity.empty')}</p>
  {:else}
    <div class="feed">
      {#each groups as group (group.day)}
        <section class="day">
          <h2 class="day-head ui">{formatDate(group.day)}</h2>
          <ul class="events ui">
            {#each group.items as item, i (i)}
              <li class="event">
                <span class="icon" class:endorsed={item.kind === 'endorsement'} aria-hidden="true">
                  <Icon name={activityIconName(item.kind)} filled={activityIconFilled(item.kind)} />
                </span>
                <span class="what">
                  <span class="kind mono">{t(KIND_KEYS[item.kind] ?? 'activity.kind_version')}</span>
                  <a class="concept" href="/concepts/{item.concept_id}">{item.canonical_form}</a>
                  <span class="summary"
                    >{item.actor?.display_name ?? t('tm.unknown_author')} {t('typo.dash')} {item.summary}</span
                  >
                </span>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
</div>

<style>
  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .empty {
    max-width: 55ch;
  }

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .feed {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    max-width: 72ch;
    margin-top: var(--space-6);
  }

  .day-head {
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    border-bottom: 1px solid var(--line);
    padding-bottom: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .events {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .event {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
  }

  .icon {
    flex-shrink: 0;
    width: 1.4em;
    text-align: center;
    color: var(--accent);
  }

  .icon.endorsed {
    color: var(--endorsed);
  }

  .what {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex-wrap: wrap;
    font-size: var(--text-sm);
  }

  .kind {
    color: var(--ink-3);
  }

  .concept {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    font-weight: 560;
  }

  .summary {
    color: var(--ink-2);
  }
</style>
