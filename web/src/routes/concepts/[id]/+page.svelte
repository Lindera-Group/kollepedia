<script lang="ts">
  /** Begreppssidan som verktygsyta (2026-07-10 redesign — see
   * .claude/plans/active/BEGREPPSSIDA_REDESIGN.md +
   * BEGREPPSSIDA_IMPL_CONTRACT.md). Layout: breadcrumb → h1 + langcode →
   * definition → version byline (+ endorse) → badge row → "Se även" →
   * VersionStrip → six tool buttons, each disclosing at most one subview. */
  import { afterNavigate, goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    api,
    ApiError,
    night4,
    type ActivityItem,
    type ConceptGraphOut,
    type ConceptListItem,
    type ConceptOut,
    type ListItemOut,
    type ListOut,
    type ProposalOut
  } from '$lib/api';
  import CollectionBadge from '$lib/components/CollectionBadge.svelte';
  import ToolLang from '$lib/concept/ToolLang.svelte';
  import ToolLists from '$lib/concept/ToolLists.svelte';
  import ToolRelations from '$lib/concept/ToolRelations.svelte';
  import ToolTalk from '$lib/concept/ToolTalk.svelte';
  import { groupRelations, relationLabel } from '$lib/concept/relations';
  import ActivityList from '$lib/components/ActivityList.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { errorMessage } from '$lib/errors';
  import VersionStrip from '$lib/components/VersionStrip.svelte';
  import ConceptTaxonomies from '$lib/taxonomy/ConceptTaxonomies.svelte';
  import SharePanel from '$lib/components/SharePanel.svelte';
  import { taxonomyValueName } from '$lib/taxonomy/valueName';
  import ConceptCombobox from '$lib/edit/ConceptCombobox.svelte';
  import EditPanel from '$lib/edit/EditPanel.svelte';
  import RelationEditor from '$lib/edit/RelationEditor.svelte';
  import EndorsePanel from '$lib/endorse/EndorsePanel.svelte';
  import AddToList from '$lib/lists/AddToList.svelte';
  import { pinLabel } from '$lib/lists/pin';
  import Icon from '$lib/icons/Icon.svelte';
  import SectionedDefinition from '$lib/sections/SectionedDefinition.svelte';
  import CommentThread from '$lib/discuss/CommentThread.svelte';
  import ProposalForm from '$lib/proposals/ProposalForm.svelte';
  import StatusBadge from '$lib/proposals/StatusBadge.svelte';
  import { buildLanes } from '$lib/timemachine/graph';
  import { formatDate, languageLabel, statusLabel, t, type TranslationKey } from '$lib/i18n.svelte';
  import { stripMarkdown } from '$lib/text';
  import { currentUser, isOrgAdmin } from '$lib/user.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  const id = $derived(page.params.id ?? '');

  // Writable derived: renders the load seed (SSR included); post-edit
  // refetches assign an override, and navigations reset it to fresh data.
  let concept = $derived<ConceptOut | null>(data.concept);
  let error = $state<string | null>(null);
  // Soft not-found (paket D): from the load seed, or from a failed client
  // retry — rendered as an informative in-page state, never an error page.
  let notFound = $derived<boolean>(data.reason === 'not_found');

  let saved = $state<string | null>(null);

  // Real write permission for THIS collection (UI-gating 2026-07-15): the
  // server's can_edit decision, so we only show write tools to those who can
  // actually use them — a viewer no longer sees edit/revise/relations at all.
  const canWrite = $derived(concept?.collection.can_write === true);
  // loggedIn gates read-but-authed affordances (watch, add-to-list) that any
  // signed-in user may use regardless of write rights — kept distinct from
  // canWrite so a viewer keeps those without seeing the write tools.
  const loggedIn = $derived(currentUser.handle !== '');

  // ── Curated vs free classification on the badge row (2026-07-12) ──
  const conceptCategories = $derived(
    concept?.taxonomies
      .filter((tx) => tx.scope === 'global')
      .flatMap((tx) => tx.values) ?? []
  );
  const collectionTaxonomies = $derived(
    concept?.taxonomies.filter((tx) => tx.scope === 'collection') ?? []
  );
  // Display-level dedup: prototype imports stored v1 category names as TAGS —
  // hide tags that merely duplicate a curated category (either language).
  const visibleTags = $derived.by(() => {
    const catNames = new Set(
      conceptCategories.flatMap((v) => [v.name.toLowerCase(), v.name_en?.toLowerCase() ?? ''])
    );
    return (concept?.head?.tags ?? []).filter(
      (tag) => !catNames.has(tag.toLowerCase()) && !tag.startsWith('part:')
    );
  });

  // ── History-aware breadcrumb: back to WHERE YOU CAME FROM (search or the
  // collection page), whose snapshot restores the exact scroll position. ──
  let backTarget = $state<'history' | 'collection'>('collection');
  let backLabel = $state('');
  afterNavigate((nav) => {
    const from = nav.from?.url.pathname;
    if (from === '/') {
      backTarget = 'history';
      backLabel = t('common.back_to_search').replace('← ', '');
    } else if (from?.startsWith('/collections/')) {
      backTarget = 'history';
      backLabel = concept?.collection.name ?? '';
    } else if (nav.from == null) {
      backTarget = 'collection';
    }
  });

  // "Hantera"-popover (gear): curation actions that would bloat the tool row.
  let manageOpen = $state(false);
  let manageTrigger = $state<HTMLButtonElement | undefined>();

  function openManaged(tool: ToolKey): void {
    manageOpen = false;
    toggleTool(tool);
  }

  $effect(() => {
    if (!manageOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        manageOpen = false;
        manageTrigger?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.manage-wrap')) manageOpen = false;
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onClick);
    };
  });

  const shareText = $derived(concept?.head ? `${concept.head.canonical_form} ${t('typo.dash')} Kollepedia NG` : '');

  // Watching (iteration 4): optimistic bell toggle + optimistic counter.
  let watching = $state(false);
  let watchBusy = $state(false);
  let watchError = $state<string | null>(null);
  let watcherCount = $state(0);

  // Change proposals + activity + discussion (iteration 4). Passive reads
  // degrade quietly on 404 while the backend is being built in parallel.
  let allProposals = $state<ProposalOut[]>([]);
  let proposalsError = $state<string | null>(null);
  let activity = $state<ActivityItem[]>([]);

  let listCount = $state(0);

  // The version DAG (Time Machine payload), fetched separately so the
  // VersionStrip + the "version X av Y" byline share one chronology.
  let graph = $state<ConceptGraphOut | null>(null);

  type ToolKey = 'edit' | 'categorize' | 'relations' | 'lists' | 'lang' | 'share' | 'activity' | 'talk';
  let activeTool = $state<ToolKey | null>(null);

  const nonMainBranches = $derived((concept?.branches ?? []).filter((b) => b.name !== 'main'));

  const versionModel = $derived.by(() => {
    if (!graph) return null;
    const { mainPath, lanes } = buildLanes(graph, 'main');
    const forkIndices = [...new Set(lanes.filter((l) => l.parent === 'main').map((l) => l.forkIndex))];
    return { mainPath, forkIndices };
  });

  const stripVersions = $derived(versionModel?.mainPath ?? (concept?.head ? [concept.head] : []));
  const stripForkIndices = $derived(versionModel?.forkIndices ?? []);

  const versionPosition = $derived.by(() => {
    const headId = concept?.head?.id;
    if (versionModel && headId) {
      const idx = versionModel.mainPath.findIndex((v) => v.id === headId);
      if (idx >= 0) return idx + 1;
    }
    return concept?.version_count ?? 1;
  });
  const versionTotal = $derived(versionModel?.mainPath.length ?? concept?.version_count ?? 1);

  const sortedProposals = $derived.by(() => {
    const open = allProposals.filter((p) => p.status === 'open');
    const rest = allProposals.filter((p) => p.status !== 'open');
    open.sort((a, b) => b.created_at.localeCompare(a.created_at));
    rest.sort((a, b) => b.created_at.localeCompare(a.created_at));
    return [...open, ...rest];
  });

  async function loadGraph(conceptId: string): Promise<void> {
    try {
      graph = await api.graph(conceptId);
    } catch {
      graph = null;
    }
  }

  async function refreshProposals(conceptId: string): Promise<void> {
    proposalsError = null;
    try {
      allProposals = await night4.proposals({ concept_id: conceptId });
    } catch (e) {
      allProposals = [];
      if (!(e instanceof ApiError && e.status === 404)) {
        proposalsError = errorMessage(e);
      }
    }
  }

  async function refreshActivity(conceptId: string): Promise<void> {
    try {
      activity = await night4.conceptActivity(conceptId, 30);
    } catch {
      activity = [];
    }
  }

  async function loadCollab(conceptId: string): Promise<void> {
    await Promise.all([refreshProposals(conceptId), refreshActivity(conceptId)]);
  }

  function onListItemAdded(): void {
    listCount += 1;
  }

  function closeTool(): void {
    activeTool = null;
  }

  function toggleTool(key: ToolKey): void {
    if (activeTool === key) {
      activeTool = null;
      return;
    }
    activeTool = key;
    if (key === 'talk') void refreshProposals(id);
    else if (key === 'activity') void refreshActivity(id);
  }

  function onLangClick(): void {
    const translations = concept?.translations ?? [];
    if (translations.length === 1) {
      void goto(`/concepts/${translations[0].concept_id}`);
      return;
    }
    // No auto-jump into the link-search form: creating a translation is the
    // primary workflow, so the tool always opens on the create/link choice.
    toggleTool('lang');
  }

  async function toggleWatch(): Promise<void> {
    if (watchBusy || !concept) return;
    const next = !watching;
    watching = next;
    watcherCount = Math.max(0, watcherCount + (next ? 1 : -1));
    watchError = null;
    watchBusy = true;
    try {
      if (next) await night4.watch(concept.id);
      else await night4.unwatch(concept.id);
    } catch (e) {
      watching = !next;
      watcherCount = Math.max(0, watcherCount + (next ? -1 : 1));
      watchError = errorMessage(e);
    } finally {
      watchBusy = false;
    }
  }

  // Lock & archive (iteration 3): fields arrive with the backend; undefined = open.
  const managesCollection = $derived(
    currentUser.is_super_admin ||
      (!!concept?.collection.organisation && isOrgAdmin(concept.collection.organisation.id))
  );
  const collectionArchived = $derived(concept?.collection.is_archived === true);
  const collectionLocked = $derived(concept?.collection.is_locked === true);
  const writeBlocked = $derived(collectionArchived || (collectionLocked && !managesCollection));
  const blockedTitle = $derived(
    collectionArchived ? t('coll.blocked_archived') : t('coll.blocked_locked')
  );

  const otherLanguage = $derived(concept?.head?.language === 'sv' ? 'en' : 'sv');

  async function load(conceptId: string, reset = true): Promise<void> {
    if (reset) concept = null;
    error = null;
    try {
      concept = await api.concept(conceptId);
      watching = (concept as ConceptOut & { watching?: boolean }).watching ?? false;
      watcherCount = concept.watcher_count ?? 0;
      listCount = concept.list_count ?? 0;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) notFound = true;
      else error = errorMessage(e);
      return;
    }
    void loadGraph(conceptId);
    void loadCollab(conceptId);
  }

  $effect(() => {
    const conceptId = id;
    const seeded = data.concept; // tracked: re-runs on client navigations
    // Subview-lokal state (länkning, relationer, diskussion, listor) bor nu i
    // Tool*-komponenterna och nollställs genom att de avmonteras här.
    activeTool = null;
    saved = null;
    watching = false;
    watchError = null;
    graph = null;
    if (seeded) {
      // Initial render comes from the load function (SSR seed) — only the
      // graph + collab extras (proposals/activity) fetch client-side.
      watching = (seeded as ConceptOut & { watching?: boolean }).watching ?? false;
      watcherCount = seeded.watcher_count ?? 0;
      listCount = seeded.list_count ?? 0;
      error = null;
      void loadGraph(conceptId);
      void loadCollab(conceptId);
    } else if (data.reason === null) {
      // SSR saw 404 with a login signal — retry with the real session.
      load(conceptId);
    }
  });

  async function onSaved(mode: 'revise' | 'branch', branchName?: string): Promise<void> {
    activeTool = null;
    await load(id, false);
    saved =
      mode === 'branch'
        ? t('concept.branch_created', { name: branchName ?? '' })
        : t('concept.version_created', { n: concept?.version_count ?? '' });
  }

  const flatRelations = $derived(
    [...groupRelations(concept?.relations ?? []).entries()].flatMap(([type, relations]) =>
      relations.map((r) => ({ ...r, typeLabel: relationLabel(type) }))
    )
  );

  const talkCount = $derived(concept?.comment_count ?? 0);
  const openPropCount = $derived(concept?.open_proposal_count ?? 0);
  const activityCount = $derived(concept?.activity_count ?? 0);
</script>

<svelte:head>
  <title>{concept?.head?.canonical_form ?? t('concept.fallback_title')} {t('typo.dash')} Kollepedia NG</title>
  {#if concept?.head}
    <meta name="description" content={stripMarkdown(concept.head.definition_md).slice(0, 160)} />
  {/if}
</svelte:head>

<div class="container">
  {#if error}
    <p class="ui">{t('concept.fetch_error', { error })}</p>
  {:else if concept?.head}
    <nav class="ui breadcrumb crumbs">
      {#if backTarget === 'history'}
        <!-- history.back() restores the origin page's snapshot INCLUDING its
             scroll position (home + collection pages both capture scrollY). -->
        <button type="button" class="back-link" onclick={() => history.back()}>
          ← {backLabel}
        </button>
      {:else}
        <a href="/collections/{concept.collection.slug}">← {concept.collection.name}</a>
      {/if}
    </nav>

    {#if collectionArchived || collectionLocked}
      <p class="coll-banner ui" class:archived={collectionArchived} role="status">
        <span class="banner-icon" aria-hidden="true"><Icon name={collectionArchived ? 'archive' : 'lock'} filled={!collectionArchived} size={15} /></span>
        {#if collectionArchived}
          {t('concept.banner_archived', { name: concept.collection.name })}
        {:else}
          {t('concept.banner_locked', { name: concept.collection.name })}
        {/if}
      </p>
    {/if}

    <article>
      <div class="title-row">
        <h1>{concept.head.canonical_form}</h1>
        <span class="langcode">{concept.head.language.toUpperCase()}</span>
      </div>

      <SectionedDefinition
        definitionMd={concept.head.definition_md}
        annotations={concept.head.annotations}
      />

      <p class="byline mono">
        {t('tm.version_x_of_y', { x: versionPosition, y: versionTotal })} ·
        <span class="status-box">{statusLabel(concept.head.status)}</span> ·
        {#if concept.head.created_by}
          <!-- Beslut 5 (2026-07-12): only the author's NAME under the
               definition — affiliation and everything else live one click
               away on the author page. -->
          <a class="author-link" href="/authors/{concept.head.created_by.handle}"
            >{concept.head.created_by.display_name}</a
          >
        {:else}
          {t('tm.unknown_author')}
        {/if}
        · {formatDate(concept.head.created_at)}
      </p>
      {#if concept.head.provenance?.kind === 'llm'}
        <p class="mono ai">{t('tm.ai_generated')} ({String(concept.head.provenance.model ?? '')})</p>
      {/if}
      {#if concept.head.note && concept.head.provenance?.kind !== 'import'}
        <!-- Import notes are boilerplate and already live in Aktivitet — only
             human justifications earn the quote treatment here. -->
        <blockquote class="version-quote">”{concept.head.note}”</blockquote>
      {/if}
      <EndorsePanel
        versionId={concept.head.id}
        endorsements={concept.head.endorsements}
        onchanged={() => load(id, false)}
      />

      <div class="badge-row">
        <CollectionBadge collection={concept.collection} />
        {#each conceptCategories as category (category.id)}
          <a class="cat-pill" href="/?category_name={encodeURIComponent(category.name)}"
            >{taxonomyValueName(category)}</a
          >
        {/each}
        {#each visibleTags as tag (tag)}
          <span class="tag-pill">#{tag}</span>
        {/each}
      </div>
      {#each collectionTaxonomies as tx (tx.taxonomy_id)}
        <p class="part-line mono">
          <span class="part-label">{tx.taxonomy_name}</span>
          {tx.values.map(taxonomyValueName).join(' · ')}
        </p>
      {/each}

      {#if flatRelations.length}
        <p class="see-also ui">
          <span class="see-also-label">{t('cpage.see_also')}</span>
          {#each flatRelations as relation, i (relation.id)}
            {i > 0 ? ' · ' : ''}<a
              href="/concepts/{relation.other_concept_id}"
              title={relation.typeLabel}>{relation.other_canonical_form}</a
            >{#if relation.other_collection_slug !== concept.collection.slug}<span
                class="rel-coll mono"> ({relation.other_collection_slug})</span
              >{/if}
          {/each}
        </p>
      {/if}

      <VersionStrip conceptId={concept.id} versions={stripVersions} forkIndices={stripForkIndices} />

      {#if saved}
        <p class="confirm ui" role="status">
          <Icon name="check" size={14} /> {saved} {t('typo.dash')} <a href="/concepts/{concept.id}/history">{t('concept.view_history')}</a>
        </p>
      {/if}

      <div class="tool-row ui" role="group" aria-label={t('cpage.tools_aria')}>
        {#if canWrite}
          <button
            type="button"
            class="btn tool-btn"
            class:active={activeTool === 'edit'}
            disabled={writeBlocked}
            aria-expanded={activeTool === 'edit'}
            aria-controls="tool-edit"
            title={writeBlocked ? blockedTitle : t('concept.edit_title')}
            onclick={() => {
              saved = null;
              toggleTool('edit');
            }}
          >
            <Icon name="edit" />
            {t('concept.edit')}
          </button>
        {/if}

        <span class="manage-wrap">
          <button
            type="button"
            class="btn tool-btn"
            class:active={manageOpen || activeTool === 'categorize' || activeTool === 'relations'}
            aria-haspopup="menu"
            aria-expanded={manageOpen}
            title={t('concept.manage_title')}
            onclick={() => (manageOpen = !manageOpen)}
            bind:this={manageTrigger}
          >
            <Icon name="gear" />
            {t('concept.manage')}
          </button>
          {#if manageOpen}
            <div class="manage-menu card ui" role="menu" aria-label={t('concept.manage')}>
              <button type="button" role="menuitem" onclick={() => openManaged('share')}>
                <Icon name="share" size={14} />
                {t('concept.share')}
              </button>
              {#if concept.translations.length === 0 && canWrite}
                <button type="button" role="menuitem" onclick={() => { manageOpen = false; onLangClick(); }}>
                  <Icon name="globe" size={14} />
                  {t('cpage.tool_lang_empty')}
                </button>
              {/if}
              {#if loggedIn}
                <button type="button" role="menuitem" onclick={() => openManaged('lists')}>
                  <Icon name="list" size={14} />
                  {listCount > 0 ? t('nav.lists') : t('list.add_button')}
                  {#if listCount > 0}<span class="count-badge">{listCount}</span>{/if}
                </button>
              {/if}
              {#if canWrite}
                <button
                  type="button"
                  role="menuitem"
                  disabled={writeBlocked}
                  onclick={() => openManaged('categorize')}
                >
                  <Icon name="category" size={14} />
                  {t('tax.categories_label')}
                </button>
                <button type="button" role="menuitem" onclick={() => openManaged('relations')}>
                  <Icon name="relation" size={14} />
                  {t('concept.relations')}
                </button>
              {/if}
            </div>
          {/if}
        </span>

        {#if loggedIn}
          <button
            type="button"
            class="btn tool-btn"
            class:watch-on={watching}
            aria-pressed={watching}
            aria-label={t('watch.aria')}
            title={watching ? t('watch.title_unwatch') : t('watch.title_watch')}
            disabled={watchBusy}
            onclick={toggleWatch}
          >
            <Icon name="bell" filled={watching} />
            {watching ? t('watch.watching') : t('watch.watch')}
            {#if watcherCount > 0}<span class="count-badge">{watcherCount}</span>{/if}
          </button>
        {/if}

        {#if concept.translations.length > 0}
          <!-- With translations the button is NAVIGATION (switch language) —
               creating/linking a translation lives under Hantera. -->
          <button
            type="button"
            class="btn tool-btn"
            class:active={activeTool === 'lang'}
            title={concept.translations.length === 1
              ? t('cpage.tool_lang_switch_title', { lang: languageLabel(concept.translations[0].language) })
              : undefined}
            aria-expanded={concept.translations.length > 1 ? activeTool === 'lang' : undefined}
            aria-controls={concept.translations.length > 1 ? 'tool-lang' : undefined}
            onclick={onLangClick}
          >
            <Icon name="globe" />
            {t('cpage.tool_lang')}
            {#if concept.translations.length === 1}
              <span class="langcode">{concept.translations[0].language.toUpperCase()}</span>
            {:else}
              <span class="count-badge tool-count">{concept.translations.length}</span>
            {/if}
          </button>
        {/if}

        <span class="tool-gap" aria-hidden="true"></span>

        <button
          type="button"
          class="btn tool-btn"
          class:active={activeTool === 'activity'}
          aria-expanded={activeTool === 'activity'}
          aria-controls="tool-activity"
          onclick={() => toggleTool('activity')}
        >
          <Icon name="pulse" />
          {t('activity.h1')}
          <span class="count-badge tool-count">{activityCount}</span>
        </button>

        <button
          type="button"
          class="btn tool-btn"
          class:active={activeTool === 'talk'}
          aria-expanded={activeTool === 'talk'}
          aria-controls="tool-talk"
          onclick={() => toggleTool('talk')}
        >
          <Icon name="talk" />
          {t('disc.title')}
          <span class="count-badge tool-count"
            >{openPropCount > 0
              ? t('cpage.tool_talk_count_with_proposals', { n: talkCount, m: openPropCount })
              : talkCount}</span
          >
        </button>
      </div>
      {#if !loggedIn}
        <p class="locked-hint ui">{t('concept.locked_hint')}</p>
      {/if}

      {#if activeTool === 'edit'}
        <div id="tool-edit" class="subview">
          <h3 class="subview-h ui">{t('concept.edit')}</h3>
          <EditPanel {concept} head={concept.head} oncancel={closeTool} onsaved={onSaved} />
        </div>
      {/if}

      {#if activeTool === 'categorize'}
        <div id="tool-categorize" class="subview">
          <h3 class="subview-h ui">{t('tax.edit')}</h3>
          <p class="subview-hint ui">{t('concept.concept_level_hint')}</p>
          <ConceptTaxonomies
            {concept}
            editable={canWrite && !writeBlocked}
            onchanged={() => load(id, false)}
          />
        </div>
      {/if}

      {#if activeTool === 'relations'}
        <div id="tool-relations" class="subview">
          <ToolRelations {concept} onchanged={() => load(id, false)} />
        </div>
      {/if}

      {#if activeTool === 'share'}
        <div id="tool-share" class="subview">
          <h3 class="subview-h ui">{t('concept.share')}</h3>
          <SharePanel conceptId={concept.id} versionId={concept.head.id} title={shareText} />
        </div>
      {/if}

      {#if activeTool === 'lists'}
        <div id="tool-lists" class="subview">
          <ToolLists concept={{ ...concept, head: concept.head }} onadded={onListItemAdded} />
        </div>
      {/if}

      {#if activeTool === 'lang'}
        <div id="tool-lang" class="subview">
          <ToolLang
            concept={{ ...concept, head: concept.head }}
            {canWrite}
            {writeBlocked}
            onchanged={() => load(id, false)}
          />
        </div>
      {/if}

      {#if activeTool === 'activity'}
        <div id="tool-activity" class="subview">
          <h3 class="subview-h ui">{t('activity.h1')}</h3>
          <ActivityList
            items={activity}
            compact
            onselect={(it) =>
              void goto(`/concepts/${id}/history${it.version_id ? `?v=${it.version_id}` : ''}`)}
          />
        </div>
      {/if}

      {#if activeTool === 'talk'}
        <div id="tool-talk" class="subview">
          <ToolTalk
            {concept}
            proposals={sortedProposals}
            {proposalsError}
            {nonMainBranches}
            {canWrite}
            onproposed={() => void refreshProposals(id)}
          />
        </div>
      {/if}
    </article>
  {:else if notFound || data.reason === 'error'}
    <EmptyState
      icon="book"
      heading={data.reason === 'error' ? t('soft404.load_error_h') : t('soft404.concept_h')}
      body={data.reason === 'error'
        ? t('soft404.load_error_body')
        : currentUser.handle
          ? t('soft404.concept_body')
          : `${t('soft404.concept_body')} ${t('soft404.login_hint')}`}
      level={1}
    >
      {#snippet actions()}
        <a class="btn-primary" href="/">{t('soft404.search_concepts')}</a>
        <a class="btn" href="/collections">{t('soft404.to_collections')}</a>
      {/snippet}
    </EmptyState>
  {:else}
    <p class="ui loading">{t('concept.loading_concept')}</p>
  {/if}
</div>

<style>
  .manage-wrap {
    position: relative;
    display: inline-flex;
  }

  .manage-menu {
    position: absolute;
    z-index: 30;
    top: calc(100% + 6px);
    left: 0;
    min-width: 200px;
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
  }

  .manage-menu button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: none;
    background: transparent;
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .manage-menu button:hover:not(:disabled) {
    background: var(--accent-soft);
  }

  .manage-menu button:disabled {
    color: var(--ink-3);
    cursor: default;
  }

  .back-link {
    border: none;
    background: none;
    padding: 0;
    font: inherit;
    color: var(--accent);
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent);
    text-underline-offset: 0.18em;
  }

  .part-line {
    font-size: var(--text-xs);
    color: var(--ink-2);
    margin: var(--space-1) 0 0;
  }

  .part-label {
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-right: var(--space-1);
  }

  .rel-coll {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .tool-gap {
    flex-basis: var(--space-6);
  }

  /* Layout-only composition on the global .breadcrumb (which owns size/rhythm). */
  .crumbs {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-4);
  }

  .coll-banner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    max-width: 65ch;
    margin: 0 0 var(--space-6);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--endorsed);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--endorsed) 9%, transparent);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .coll-banner.archived {
    border-color: var(--del-strong);
    background: var(--del-wash);
  }

  .banner-icon {
    display: inline-flex;
    flex-shrink: 0;
    color: var(--endorsed);
  }

  .title-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .title-row h1 {
    margin-bottom: 0;
  }

  .langcode {
    display: inline-flex;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    background: var(--bg-sunken);
    color: var(--ink-2);
    border-radius: var(--radius-sm);
    padding: 0.1em 0.4em;
    white-space: nowrap;
  }

  .byline {
    color: var(--ink-3);
    margin: var(--space-6) 0 var(--space-1);
  }

  .byline .author-link {
    color: inherit;
    text-decoration-color: color-mix(in srgb, var(--ink-3) 45%, transparent);
  }

  .byline .author-link:hover {
    color: var(--accent);
  }

  .status-box {
    color: var(--ink-2);
    border: 1px dashed var(--ink-3);
    border-radius: var(--radius-sm);
    padding: 0 0.35em;
  }

  .ai {
    color: var(--accent);
  }

  .version-quote {
    margin: var(--space-1) 0 var(--space-2);
    padding-left: var(--space-3);
    border-left: 3px solid var(--line);
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }

  .badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    margin: var(--space-6) 0 var(--space-4);
  }

  .see-also {
    max-width: 70ch;
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .see-also-label {
    color: var(--ink-3);
    margin-right: var(--space-1);
  }

  .confirm {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
    color: var(--ins-strong);
  }

  .tool-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    border-top: 1px solid var(--line);
    padding-top: var(--space-4);
    margin: var(--space-6) 0 var(--space-1);
  }

  .tool-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .tool-btn.active {
    background: var(--ink);
    color: var(--bg);
    border-color: var(--ink);
  }

  .tool-btn.active .tool-count {
    background: var(--bg);
    color: var(--ink);
  }

  .tool-btn.watch-on {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .tool-btn.watch-on:hover {
    background: transparent;
    color: var(--ins-strong);
  }

  .tool-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .tool-btn:disabled:hover {
    background: transparent;
    color: var(--ink);
  }

  .locked-hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0 0 var(--space-4);
  }

  .loading {
    color: var(--ink-3);
  }      @media (max-width: 640px) {
    .tool-row {
      gap: var(--space-1);
    }
  }
</style>
