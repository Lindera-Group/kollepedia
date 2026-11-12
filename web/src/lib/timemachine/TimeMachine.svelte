<script lang="ts">
  import { tick, untrack } from 'svelte';
  import { api, type ActivityItem, type ConceptGraphOut, type VersionOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { currentUser } from '$lib/user.svelte';
  import { activityIconFilled, activityIconName } from '$lib/discuss/activity';
  import { blameChain, tokenAges } from './blame';
  import { buildLanes, buildPath, stepTypes as stepTypesOf } from './graph';
  import { Playback } from './playback.svelte';
  import {
    buildTransition,
    restSpans,
    DEFAULT_ORDER,
    type AnimationOrder,
    type PillChange
  } from './script';
  import EndorsePanel from '$lib/endorse/EndorsePanel.svelte';
  import AnimatedText from './AnimatedText.svelte';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import HistoryEditPanel from './HistoryEditPanel.svelte';
  import HoverCard from './HoverCard.svelte';
  import SharePanel from '$lib/components/SharePanel.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { iconMarkup } from '$lib/icons/icons';
  import MetaPills from './MetaPills.svelte';
  import StaticDiff from './StaticDiff.svelte';
  import Timeline from './Timeline.svelte';
  import VersionTable from './VersionTable.svelte';
  import { formatDate, languageLabel, statusLabel, t, type TranslationKey } from '$lib/i18n.svelte';
  import { stripMarkdown } from '$lib/text';

  /** A request to move the playhead to a specific version, issued from OUTSIDE
   * (the history page's activity list / a `?v=` deep link). Rows that carry a
   * `version_id` seek directly; rows that don't (e.g. a concept-level comment)
   * seek to the latest version at/before `before`. A fresh object is expected
   * per request so repeated clicks on the same row still re-trigger the effect. */
  interface SeekRequest {
    versionId?: string | null;
    before?: string | null;
  }

  interface Props {
    graph: ConceptGraphOut;
    /** Called after a successful write (promote) so the owner can refetch the graph. */
    onchanged?: () => void;
    /** Concept-level activity feed (Iteration 4) — powers the "since last version"
     * pocket card only; the full list itself is rendered by the history page. */
    activity?: ActivityItem[];
    /** `?v=<version_id>` deep link — applied once, silently ignored if unknown. */
    initialVersionId?: string | null;
    /** See {@link SeekRequest}. */
    seekRequest?: SeekRequest | null;
    /** Fires whenever the playhead settles on/heads toward a different version
     * — lets the history page keep its activity list's highlight in sync. */
    onversionchange?: (versionId: string) => void;
  }

  let {
    graph,
    onchanged = () => {},
    activity = [],
    initialVersionId = null,
    seekRequest = null,
    onversionchange = () => {}
  }: Props = $props();

  let branchName = $state('main');
  let pendingSeekVersionId: string | null = $state(null);
  let orderMode = $state<AnimationOrder>(DEFAULT_ORDER);

  const pathModel = $derived(buildPath(graph, branchName));
  const laneModel = $derived(buildLanes(graph, branchName));
  const versions = $derived(pathModel.versions);
  const steps = $derived(stepTypesOf(graph, versions));
  const transitions = $derived(
    versions.slice(1).map((b, i) => buildTransition(versions[i], b, orderMode))
  );
  const engine = $derived(new Playback(versions, transitions));

  /** Shared by the fork controls in Timeline AND the branch event card below. */
  function switchToBranch(name: string, anchorId: string): void {
    pendingSeekVersionId = anchorId;
    branchName = name;
  }

  /** Off-path ids (e.g. a proposal's branch head) switch to the branch whose
   * path contains the version; truly unknown ids are silently ignored. */
  function seekToVersionOnAnyPath(versionId: string): void {
    for (const branch of graph.branches) {
      if (branch.name === branchName) continue;
      const path = buildPath(graph, branch.name).versions;
      if (path.some((v) => v.id === versionId)) {
        switchToBranch(branch.name, versionId);
        return;
      }
    }
  }

  // `?v=` deep link: applied once, against whatever path is current at first
  // render (the default 'main'). Branch ids switch path; unknown ids no-op.
  let appliedInitialSeek = $state(false);
  $effect(() => {
    if (appliedInitialSeek || versions.length === 0) return;
    appliedInitialSeek = true;
    if (!initialVersionId) return;
    const index = versions.findIndex((v) => v.id === initialVersionId);
    if (index >= 0) engine.seek(index);
    else seekToVersionOnAnyPath(initialVersionId);
  });

  // Activity-list → player sync (two-way, other half is onversionchange below).
  // A fresh `seekRequest` object is expected per click, so this re-fires even
  // when the same row is clicked twice in a row.
  $effect(() => {
    const request = seekRequest;
    if (!request) return;
    let index = -1;
    if (request.versionId) {
      index = versions.findIndex((v) => v.id === request.versionId);
      if (index < 0) {
        engine.pause();
        seekToVersionOnAnyPath(request.versionId);
        return;
      }
    } else if (request.before) {
      const target = new Date(request.before).getTime();
      versions.forEach((v, i) => {
        if (new Date(v.created_at).getTime() <= target) index = i;
      });
    }
    if (index >= 0) {
      engine.pause();
      engine.seek(index);
    }
  });

  async function toggleOrder(): Promise<void> {
    const position = engine.position;
    const wasPlaying = engine.playing;
    engine.pause();
    orderMode = orderMode === 'sequential' ? 'global' : 'sequential';
    await tick();
    engine.seek(position);
    if (wasPlaying) engine.play();
  }

  const versionIds = $derived(versions.map((v) => v.id));
  const titleBlame = $derived(
    blameChain(versions.map((v) => v.canonical_form), versionIds)
  );
  const defBlame = $derived(
    blameChain(versions.map((v) => stripMarkdown(v.definition_md)), versionIds)
  );

  let stageEl: HTMLElement | undefined = $state();
  $effect(() => {
    const el = stageEl;
    const current = engine;
    // untrack: attach() runs applyFrame(), which reads engine.position — without
    // untrack this effect would re-run (and destroy the engine) on every frame.
    if (el) untrack(() => current.attach(el));
    // Dev/testing hook: lets acceptance tests drive playback deterministically.
    (window as unknown as { __timeMachine?: Playback }).__timeMachine = current;
    return () => current.destroy();
  });

  // After a branch switch, resume at the version where the fork sits.
  $effect(() => {
    if (pendingSeekVersionId === null) return;
    const index = versions.findIndex((v) => v.id === pendingSeekVersionId);
    pendingSeekVersionId = null;
    if (index >= 0) engine.seek(index);
  });

  let staticMode = $state(
    typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
  );
  let inkOn = $state(false);

  function toggleInk(): void {
    // Ink now renders continuously — during transitions it becomes the
    // colour-free diff variant (deleted text fades+collapses, new text in
    // heavy ink), so no snap-to-rest is needed.
    inkOn = !inkOn;
  }

  const single = $derived(versions.length < 2);
  const singleSpans = $derived(single && versions[0] ? restSpans(versions[0]) : null);
  const T = $derived(transitions[engine.displayIndex]);

  /** Static view: at rest on version i, show the change that PRODUCED it
   * (transition i-1→i) so the diff matches the author/note in the panel.
   * At the origin (i=0) there is no incoming change; mid-flight, the same
   * pair as the animated stage. */
  const staticT = $derived.by(() => {
    if (!engine.atRest) return T;
    const i = Math.round(engine.position);
    return i > 0 ? transitions[i - 1] : null;
  });
  const originSpans = $derived(
    staticMode && staticT === null && versions[0] ? restSpans(versions[0]) : null
  );

  const aVersion = $derived(versions[engine.displayIndex]);
  const bVersion = $derived(versions[Math.min(engine.displayIndex + 1, versions.length - 1)]);
  const shown = $derived(engine.swapped ? bVersion : aVersion);
  const focusVersion = $derived(versions[engine.focusIndex] ?? versions[0]);

  /** Index of focusVersion within the current path — read via the MEMOIZED
   * focusVersion rune rather than engine.focusIndex directly. engine.focusIndex
   * is a plain getter over engine.position ($state, ticks every rAF frame
   * during playback); routing through it here would make the event-card/pocket
   * deriveds below recompute (fresh arrays) every frame instead of only at
   * version boundaries, undermining the "no flicker" requirement. focusVersion
   * itself already absorbs that per-frame churn (Svelte only propagates a
   * derived's change when its VALUE differs, and focusVersion's value — a
   * VersionOut reference — is stable within a whole transition). */
  const focusPathIndex = $derived(versions.indexOf(focusVersion));

  const restSide = $derived.by((): 'a' | 'b' | null => {
    if (!engine.atRest) return null;
    return Math.round(engine.position) > engine.displayIndex ? 'b' : 'a';
  });

  const blameArgs = $derived.by(() => {
    const i = engine.displayIndex;
    return {
      titleA: titleBlame[i] ?? null,
      titleB: titleBlame[i + 1] ?? null,
      defA: defBlame[i] ?? null,
      defB: defBlame[i + 1] ?? null,
      agesTitleA: titleBlame[i] ? tokenAges(titleBlame[i], versionIds, i) : null,
      agesTitleB: titleBlame[i + 1] ? tokenAges(titleBlame[i + 1], versionIds, i + 1) : null,
      agesDefA: defBlame[i] ? tokenAges(defBlame[i], versionIds, i) : null,
      agesDefB: defBlame[i + 1] ? tokenAges(defBlame[i + 1], versionIds, i + 1) : null
    };
  });

  const singlePills = $derived.by((): PillChange[] =>
    (versions[0]?.tags ?? []).map((tag) => ({ label: tag, state: 'kept' as const }))
  );

  let hover = $state<{ vid: string; x: number; y: number } | null>(null);
  const hoverVersion = $derived(
    hover ? (graph.versions.find((v) => v.id === hover?.vid) ?? null) : null
  );

  /** Author-tier hover (bug fix): all text by the hovered token's author
   * lights up softly, not only the single introducing version's tokens. */
  const authorByVid = $derived(
    new Map(graph.versions.map((v) => [v.id, v.created_by?.id ?? null]))
  );
  const hoverAuthorId = $derived(hoverVersion?.created_by?.id ?? null);

  function onHoverToken(vid: string | null, event: MouseEvent | null): void {
    if (!vid || !event || !engine.atRest) {
      hover = null;
      return;
    }
    hover = { vid, x: event.clientX, y: event.clientY };
  }

  const STEP_KEYS: Record<string, TranslationKey> = {
    revised_from: 'tm.step_revised',
    branched_from: 'tm.step_branched',
    synthesized_from: 'tm.step_synthesized',
    translated_from: 'tm.step_translated',
    promoted_from: 'tm.step_promoted'
  };

  function stepLabel(step: string): string {
    const key = STEP_KEYS[step];
    return key ? t(key) : step;
  }

  // Promote (VISION §4.1): a new head copies this content with a back-edge.
  let promoting = $state(false);
  let promoteError = $state<string | null>(null);
  const canPromote = $derived(
    engine.atRest &&
      !!focusVersion &&
      graph.branches.find((b) => b.name === 'main')?.head_version_id !== focusVersion.id
  );

  async function promoteFocus(): Promise<void> {
    if (!focusVersion || promoting) return;
    promoting = true;
    promoteError = null;
    try {
      await api.promote(graph.concept_id, {
        version_id: focusVersion.id,
        note: t('tm.note_restored')
      });
      onchanged();
    } catch (e) {
      promoteError = errorMessage(e);
    } finally {
      promoting = false;
    }
  }

  // Edit-from-history (VISION §4.1 — history is immutable, editing creates a
  // new version at a chosen target). The base is FROZEN at open time so a
  // moving playhead can't swap the version under the form mid-edit.
  let editBase = $state<{ version: VersionOut; number: number } | null>(null);
  let shareOpen = $state(false);

  function openEdit(): void {
    if (!focusVersion || !engine.atRest) return;
    engine.pause();
    editBase = { version: focusVersion, number: focusPathIndex + 1 };
  }

  function closeEdit(saved: boolean): void {
    editBase = null;
    if (saved) onchanged();
  }

  // Notify the history page's activity list so its highlight follows the
  // player (the other half of the two-way sync — `seekRequest` above is the
  // reverse direction). focusVersion only changes AT version boundaries (see
  // Playback.focusIndex), never per animation frame, so this is cheap.
  let lastNotifiedVersionId: string | null = null;
  $effect(() => {
    const id = focusVersion?.id ?? null;
    if (id && id !== lastNotifiedVersionId) {
      lastNotifiedVersionId = id;
      onversionchange(id);
    }
  });

  // ── Event cards (branch / merge / endorsed) — under the version-info card ──

  interface EventCard {
    key: string;
    kind: 'branch' | 'merge' | 'endorsed';
    branchName?: string;
    anchorId?: string;
    org?: string;
  }

  /** Cards for the CURRENT focus version: one per branch forking from here,
   * one if this version is a synthesis (true cross-branch merge — a promote's
   * back-edge is a different, already-labelled step, not a merge card), one
   * if it carries an active endorsement. Computed from the FULL graph (not
   * just the selected path) so nested/off-path forks still surface. */
  const eventCards = $derived.by((): EventCard[] => {
    const v = focusVersion;
    if (!v) return [];
    const cards: EventCard[] = [];

    for (const edge of graph.edges) {
      if (edge.edge_type !== 'branched_from' || edge.parent_id !== v.id) continue;
      const child = graph.versions.find((c) => c.id === edge.child_id);
      const branch = child ? graph.branches.find((b) => b.id === child.branch_id) : undefined;
      if (!child || !branch) continue;
      cards.push({ key: `branch-${branch.id}`, kind: 'branch', branchName: branch.name, anchorId: child.id });
    }

    if (steps[focusPathIndex] === 'synthesized_from') {
      const extra = graph.edges.find(
        (e) => e.child_id === v.id && e.edge_type === 'synthesized_from' && e.ordinal > 0
      );
      const parent = extra ? graph.versions.find((p) => p.id === extra.parent_id) : undefined;
      const branch = parent ? graph.branches.find((b) => b.id === parent.branch_id) : undefined;
      if (branch) cards.push({ key: 'merge', kind: 'merge', branchName: branch.name });
    }

    // One card per ACTIVE stamp — several organisations may flag the same
    // version (coexistence-first canon, endorsement rework 2026-07-11).
    for (const stamp of v.endorsements.filter((e) => !e.withdrawn_at)) {
      cards.push({
        key: `endorsed-${stamp.id}`,
        kind: 'endorsed',
        org: stamp.organisation?.name ?? stamp.body
      });
    }

    return cards;
  });

  // ── Anti-flutter pocket: comments/proposals between the previous and the
  // current version's dates. Simplification (noted in the handoff report):
  // ticks at VERSION BOUNDARIES rather than mid-transition frame progress —
  // engine.focusIndex only changes at boundaries, so the card never flickers. ──

  const POCKET_KINDS = new Set<ActivityItem['kind']>([
    'comment',
    'proposal',
    'proposal_merged',
    'proposal_rejected',
    'proposal_withdrawn'
  ]);

  const pocketItems = $derived.by((): ActivityItem[] => {
    const i = focusPathIndex;
    if (i <= 0) return [];
    const prev = versions[i - 1];
    const curr = versions[i];
    if (!prev || !curr) return [];
    const from = new Date(prev.created_at).getTime();
    const to = new Date(curr.created_at).getTime();
    return activity
      .filter((a) => POCKET_KINDS.has(a.kind))
      .filter((a) => {
        const at = new Date(a.at).getTime();
        return at > from && at <= to;
      })
      .sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  });

  const pocketCommentsCount = $derived(pocketItems.filter((i) => i.kind === 'comment').length);
  const pocketProposalsCount = $derived(pocketItems.length - pocketCommentsCount);
  const pocketVersionLabel = $derived(`v${focusPathIndex}`);

  /** Icon+count fragments, injected into `hist.events_since` via {@html} —
   * iconMarkup() exists exactly for this (string-template, non-Svelte
   * contexts; see icons.ts). Values are fully controlled, no user input. */
  function pocketMetric(icon: 'talk' | 'proposal', count: number): string {
    return (
      `<span class="pocket-metric"><svg viewBox="0 0 20 20" width="13" height="13" aria-hidden="true">` +
      `${iconMarkup(icon)}</svg>${count}</span>`
    );
  }

  const pocketCounterHtml = $derived(
    t('hist.events_since', {
      comments: pocketMetric('talk', pocketCommentsCount),
      proposals: pocketMetric('proposal', pocketProposalsCount),
      version: pocketVersionLabel
    })
  );

  const pocketCounterSrText = $derived(
    t('hist.events_since', {
      comments: String(pocketCommentsCount),
      proposals: String(pocketProposalsCount),
      version: pocketVersionLabel
    })
  );

  const POCKET_KIND_KEYS: Record<string, TranslationKey> = {
    comment: 'activity.kind_comment',
    proposal: 'activity.kind_proposal',
    proposal_merged: 'activity.kind_proposal_merged',
    proposal_rejected: 'activity.kind_proposal_rejected',
    proposal_withdrawn: 'activity.kind_proposal_withdrawn'
  };

  let pocketShowAll = $state(false);
  // Paused/scrubbed → the expanded list (spec decision); reset the "show all"
  // toggle whenever the interval itself changes, not on every play/pause flip.
  $effect(() => {
    pocketItems;
    pocketShowAll = false;
  });
  const pocketVisibleItems = $derived(pocketShowAll ? pocketItems : pocketItems.slice(0, 3));
</script>

<div class="tm">
  <div class="toolbar ui">
    <div class="left">
      <span class="mono">{graph.collection.name}</span>
      <span class="count mono">{versions.length} {t('common.versions')}</span>
      {#if branchName !== 'main'}
        <span class="pill branch-pill">{t('tm.branch_prefix')} {branchName}</span>
      {/if}
    </div>
    <div class="right">
      <button
        class="btn btn-quiet"
        aria-pressed={orderMode === 'global'}
        onclick={toggleOrder}
        title={t('tm.order_title')}
        >{t('tm.order')}: {orderMode === 'sequential' ? t('tm.order_sequential') : t('tm.order_global')}</button
      >
      <button
        class="btn btn-quiet"
        class:active={inkOn}
        aria-pressed={inkOn}
        onclick={toggleInk}
        title={t('tm.ink_title')}>{t('tm.ink_mode')}</button
      >
      <button
        class="btn btn-quiet"
        class:active={staticMode}
        aria-pressed={staticMode}
        onclick={() => (staticMode = !staticMode)}
        title={t('tm.static_title')}>{t('tm.static_view')}</button
      >
    </div>
  </div>

  <Timeline {engine} lanes={laneModel} {branchName} onSelectBranch={switchToBranch} />

  {#if inkOn && !staticMode}
    <div class="ink-legend ui" role="note" aria-label={t('tm.ink_legend_aria')}>
      <span class="ink-sample" style="--age: 1">{t('tm.ink_oldest')}</span>
      <span class="ink-sample" style="--age: 0.62">{t('tm.ink_older')}</span>
      <span class="ink-sample" style="--age: 0.3">{t('tm.ink_later')}</span>
      <span class="ink-sample" style="--age: 0">{t('tm.ink_current')}</span>
      <span class="hint">{t('tm.ink_hover_hint')}</span>
    </div>
  {/if}

  <div class="body">
    <div class="stage-wrap">
      {#if staticMode && staticT}
        <StaticDiff transition={staticT} />
      {:else if staticMode && originSpans && versions[0]}
        <div class="static-origin">
          <p class="mono origin-note">{t('vt.origin')}</p>
          <h1 class="tm-title">{versions[0].canonical_form}</h1>
          <div class="tm-def">
            <AnimatedText spans={originSpans.def} restSide="a" blameA={defBlame[0]} />
          </div>
        </div>
      {:else}
        <div
          class="tm-stage"
          class:ink={inkOn}
          bind:this={stageEl}
          aria-hidden="true"
        >
          <h1 class="tm-title">
            {#if single && singleSpans}
              <AnimatedText spans={singleSpans.title} restSide="a" blameA={titleBlame[0]} onhover={onHoverToken} hoverVid={hover?.vid ?? null}
                {hoverAuthorId}
                {authorByVid} />
            {:else if T}
              <AnimatedText
                spans={T.title}
                blameA={blameArgs.titleA}
                blameB={blameArgs.titleB}
                agesA={blameArgs.agesTitleA}
                agesB={blameArgs.agesTitleB}
                {restSide}
                hoverVid={hover?.vid ?? null}
                {hoverAuthorId}
                {authorByVid}
                inkOn={inkOn}
                typedBreaks={engine.typedBreaks}
                goneDelBreaks={engine.goneDelBreaks}
                onhover={onHoverToken}
              />
            {/if}
          </h1>

          <div class="fields ui">
            <span
              class="field"
              class:pulse={T?.fields.some((f) => f.field === 'status')}
              >{statusLabel(shown?.status ?? '')}</span
            >
            <span class="field" class:pulse={T?.fields.some((f) => f.field === 'language')}
              >{languageLabel(shown?.language ?? '')}</span
            >
            <span class="field date">{shown ? formatDate(shown.created_at) : ''}</span>
            {#if T?.formattingOnly && !engine.atRest}
              <span class="field fmt-only" role="status"><Icon name="edit" size={14} /> {t('tm.formatting_only')}</span>
            {/if}
          </div>

          <MetaPills pills={single ? singlePills : (T?.pills ?? [])} />

          <div class="tm-def">
            {#if single && singleSpans}
              <AnimatedText spans={singleSpans.def} restSide="a" blameA={defBlame[0]} onhover={onHoverToken} hoverVid={hover?.vid ?? null}
                {hoverAuthorId}
                {authorByVid} />
            {:else if T}
              <AnimatedText
                spans={T.def}
                blameA={blameArgs.defA}
                blameB={blameArgs.defB}
                agesA={blameArgs.agesDefA}
                agesB={blameArgs.agesDefB}
                {restSide}
                hoverVid={hover?.vid ?? null}
                {hoverAuthorId}
                {authorByVid}
                inkOn={inkOn}
                typedBreaks={engine.typedBreaks}
                goneDelBreaks={engine.goneDelBreaks}
                onhover={onHoverToken}
              />
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <div class="side">
      <aside class="panel card ui" aria-label={t('tm.version_info_aria')}>
        <p class="mono vnum">
          {t('tm.version_x_of_y', { x: engine.focusIndex + 1, y: versions.length })}
          {#if !engine.atRest}<span class="flight">{t('tm.in_flight')}</span>{/if}
        </p>
        {#if focusVersion}
          <p class="author">
            <strong><AuthorLink user={focusVersion.created_by} /></strong>
            {#if focusVersion.created_by?.affiliation}
              <span class="aff">{focusVersion.created_by.affiliation}</span>
            {/if}
          </p>
          <p class="mono when">{formatDate(focusVersion.created_at)}</p>
          {#if engine.focusIndex > 0 && steps[engine.focusIndex]}
            <p class="step">{stepLabel(steps[engine.focusIndex] ?? '')}</p>
          {/if}
          {#if focusVersion.provenance?.kind === 'llm'}
            <p class="prov ai">
              {t('tm.ai_generated')} · {String(focusVersion.provenance.model ?? '')}
            </p>
          {:else if focusVersion.provenance?.kind === 'import'}
            <p class="prov">{t('tm.imported_from', { source: String(focusVersion.provenance.collection ?? t('tm.source_fallback')) })}</p>
          {/if}
          {#if focusVersion.note}
            <blockquote class="note">”{focusVersion.note}”</blockquote>
          {/if}
          <button
            type="button"
            class="btn btn-quiet share-toggle"
            aria-expanded={shareOpen}
            onclick={() => (shareOpen = !shareOpen)}
          >
            <Icon name="share" size={14} />
            {t('concept.share')}
          </button>
          {#if shareOpen}
            <SharePanel
              conceptId={graph.concept_id}
              versionId={focusVersion.id}
              title={`${focusVersion.canonical_form} ${t('typo.dash')} Kollepedia NG`}
            />
          {/if}
          <EndorsePanel
            versionId={focusVersion.id}
            endorsements={focusVersion.endorsements}
            {onchanged}
          />
          {#if canPromote}
            <button
              class="btn promote-btn"
              onclick={promoteFocus}
              disabled={promoting || !currentUser.handle}
              title={currentUser.handle ? t('tm.promote_title_can') : t('tm.promote_title_locked')}
            >
              {promoting ? t('tm.promoting') : t('tm.promote')}
            </button>
            {#if promoteError}
              <p class="promote-error" role="alert">{promoteError}</p>
            {/if}
          {/if}
          {#if engine.atRest && !editBase}
            <button
              class="btn promote-btn"
              onclick={openEdit}
              disabled={!currentUser.handle}
              title={currentUser.handle ? t('tm.edit_title_can') : t('tm.promote_title_locked')}
            >
              {t('tm.edit_version', { x: engine.focusIndex + 1 })}
            </button>
          {/if}
        {/if}
      </aside>

      {#each eventCards as card (card.key)}
        <div class="evcard {card.kind}">
          <span class="ico">
            {#if card.kind === 'branch'}
              <Icon name="branch" size={16} />
            {:else if card.kind === 'merge'}
              <Icon name="merge" size={16} />
            {:else}
              <Icon name="star" filled size={16} />
            {/if}
          </span>
          <div class="evtext">
            {#if card.kind === 'branch'}
              <p><strong>{t('hist.branch_from_here')}</strong> {card.branchName}</p>
              <button
                type="button"
                class="btn btn-quiet branch-link"
                onclick={() => switchToBranch(card.branchName ?? '', card.anchorId ?? '')}
              >
                {t('hist.show_branch')}
              </button>
            {:else if card.kind === 'merge'}
              <p>{t('hist.merge_here', { branch: card.branchName ?? '' })}</p>
            {:else}
              <p>{t('hist.endorsed_by', { org: card.org ?? '' })}</p>
            {/if}
          </div>
        </div>
      {/each}

      {#if pocketItems.length > 0}
        <div class="evcard pocket">
          <p class="pocket-counter">
            <span aria-hidden="true">{@html pocketCounterHtml}</span>
            <span class="sr-only">{pocketCounterSrText}</span>
            {#if engine.playing}
              <span class="hint">{t('typo.dash')} {t('hist.pause_to_read')}</span>
            {/if}
          </p>
          {#if !engine.playing}
            <ul class="pocket-list">
              {#each pocketVisibleItems as item, i (item.kind + item.at + i)}
                <li>
                  <span class="mono date">{formatDate(item.at)}</span>
                  <span class="ico">
                    <Icon name={activityIconName(item.kind)} filled={activityIconFilled(item.kind)} size={12} />
                  </span>
                  <span class="mono kind">{t(POCKET_KIND_KEYS[item.kind] ?? 'activity.kind_comment')}</span>
                  <AuthorLink user={item.actor} fallback="" />{#if item.summary}{t('typo.dash')} {item.summary}{/if}
                </li>
              {/each}
            </ul>
            {#if !pocketShowAll && pocketItems.length > 3}
              <button type="button" class="btn btn-quiet show-all" onclick={() => (pocketShowAll = true)}>
                {t('hist.show_all', { count: pocketItems.length })}
              </button>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
  </div>

  {#if editBase}
    <HistoryEditPanel
      {graph}
      version={editBase.version}
      versionNumber={editBase.number}
      oncancel={() => closeEdit(false)}
      onsaved={() => closeEdit(true)}
    />
  {/if}

  <p class="sr-only" aria-live="polite">
    {#if engine.atRest && focusVersion}
      {t('tm.version_x_of_y', { x: engine.focusIndex + 1, y: versions.length })}, {focusVersion.canonical_form},
      {formatDate(focusVersion.created_at)}, {t('tm.sr_by')} {focusVersion.created_by?.display_name ?? t('tm.unknown')}.
    {/if}
  </p>

  <VersionTable
    {versions}
    stepTypes={steps}
    focusIndex={engine.focusIndex}
    onJump={(i) => {
      engine.pause();
      engine.seek(i);
    }}
  />

  <HoverCard version={hoverVersion} x={hover?.x ?? 0} y={hover?.y ?? 0} />
</div>

<style>
  .tm {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .toolbar .left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    color: var(--ink-3);
  }

  .branch-pill {
    border-color: var(--accent);
    color: var(--accent);
  }

  .toolbar .right {
    display: flex;
    gap: var(--space-2);
  }

  .toolbar .active {
    background: var(--ink);
    color: var(--bg);
  }

  .ink-legend {
    display: flex;
    align-items: baseline;
    gap: var(--space-4);
    font-size: var(--text-sm);
  }

  /* Same three-channel formula as the stage text (see AnimatedText). */
  .ink-sample {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    color: color-mix(in oklab, var(--ink) calc(100% - var(--age, 0) * 82%), var(--sepia));
    opacity: calc(1 - var(--age, 0) * 0.34);
    font-weight: calc(650 - var(--age, 0) * 330);
  }

  .ink-legend .hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: var(--space-8);
    align-items: start;
    min-height: 380px;
  }

  @media (max-width: 860px) {
    .body {
      grid-template-columns: 1fr;
    }
  }

  .static-origin {
    padding: var(--space-4) 0;
  }

  .origin-note {
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: var(--text-xs);
    margin-bottom: var(--space-2);
  }

  .tm-stage {
    padding: var(--space-4) 0;
  }

  .tm-title {
    font-size: var(--text-display);
    font-weight: 600;
    margin-bottom: var(--space-4);
    min-height: 1.2em;
  }

  .fields {
    display: flex;
    gap: var(--space-4);
    margin-bottom: var(--space-3);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .field {
    border-radius: var(--radius-sm);
    padding: 0.1em 0.4em;
    margin: -0.1em -0.4em;
  }

  /* Changed fields pulse softly while the transition plays. */
  .field.pulse {
    background-color: color-mix(
      in srgb,
      var(--accent) calc(var(--pm, 0) * (1 - var(--pm, 0)) * 4 * 25%),
      transparent
    );
  }

  .date {
    color: var(--ink-3);
  }

  /* Formatting-only transitions have no prose diff to animate — this chip
     fades in and out with the transition (parabola over --pm) instead. */
  .fmt-only {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    color: var(--accent);
    opacity: calc(var(--pm, 0) * (1 - var(--pm, 0)) * 4);
    background-color: color-mix(
      in srgb,
      var(--accent) calc(var(--pm, 0) * (1 - var(--pm, 0)) * 4 * 12%),
      transparent
    );
  }

  .tm-def {
    font-size: var(--text-body-lg);
    line-height: 1.75;
    max-width: 62ch;
    margin-top: var(--space-4);
  }

  /* The version-info card + the event/pocket cards below it share this
     sticky column (same width, ui-guardrails §15: the .side wrapper owns
     the stickiness so the cards scroll together as one unit). */
  .side {
    position: sticky;
    top: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .panel {
    font-size: var(--text-sm);
  }

  .vnum {
    color: var(--ink-3);
    margin-bottom: var(--space-3);
  }

  .flight {
    color: var(--accent);
  }

  .author strong {
    font-size: var(--text-base);
  }

  .author .aff {
    display: block;
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .when {
    color: var(--ink-3);
  }

  .step {
    color: var(--accent);
    font-weight: 500;
  }

  .prov {
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .prov.ai {
    color: var(--accent);
  }

  .note {
    margin: var(--space-3) 0;
    padding-left: var(--space-3);
    border-left: 3px solid var(--line);
    font-family: var(--font-serif);
    font-style: italic;
    font-size: var(--text-base);
    color: var(--ink-2);
  }


  .share-toggle {
    font-size: var(--text-xs);
    margin-bottom: var(--space-2);
  }

  .promote-btn {
    margin-top: var(--space-3);
    width: 100%;
  }

  .promote-error {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  /* ── Event cards (branch/merge/endorsed) + the anti-flutter pocket ── */

  .evcard {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--line);
    border-left: 3px solid var(--ink-3);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    font-size: var(--text-sm);
  }

  .evcard p {
    margin: 0;
  }

  .evcard .ico {
    flex: 0 0 auto;
    display: inline-flex;
    margin-top: 0.15em;
  }

  .evcard.branch {
    border-left-color: var(--accent);
  }

  .evcard.branch .ico {
    color: var(--accent);
  }

  .evcard.merge {
    border-left-color: var(--ins-strong);
  }

  .evcard.merge .ico {
    color: var(--ins-strong);
  }

  .evcard.endorsed {
    border-left-color: var(--endorsed);
  }

  .evcard.endorsed .ico {
    color: var(--endorsed);
  }

  .evtext {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
  }

  .branch-link {
    font-size: var(--text-xs);
    padding: 0.15em 0.6em;
  }

  .evcard.pocket {
    flex-direction: column;
    align-items: stretch;
  }

  .pocket-counter {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    color: var(--ink-2);
  }

  .pocket-counter :global(.pocket-metric) {
    display: inline-flex;
    align-items: center;
    gap: 0.3em;
    font-family: var(--font-mono);
  }

  .pocket-counter .hint {
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .pocket-list {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
  }

  .pocket-list li {
    padding: var(--space-1) 0;
    border-top: 1px dashed var(--line);
    color: var(--ink-2);
  }

  .pocket-list li:first-child {
    border-top: none;
  }

  .pocket-list .date {
    color: var(--ink-3);
    margin-right: var(--space-1);
  }

  .pocket-list .ico {
    color: var(--ink-3);
  }

  .pocket-list .kind {
    color: var(--ink-3);
    margin-right: var(--space-1);
  }

  .show-all {
    align-self: flex-start;
    margin-top: var(--space-2);
    font-size: var(--text-xs);
    padding: 0.15em 0.6em;
  }

</style>
