<script lang="ts">
  import { page } from '$app/state';
  import { api, ApiError, night4, type ActivityItem, type ConceptGraphOut } from '$lib/api';
  import ActivityList from '$lib/components/ActivityList.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { stripMarkdown } from '$lib/text';
  import TimeMachine from '$lib/timemachine/TimeMachine.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  const id = $derived(page.params.id ?? '');

  // Writable derived: renders the load seed (SSR included); post-write
  // refetches assign an override, and navigations reset it to fresh data.
  // A hard not-found is a soft in-page state (paket D), never an error page.
  let graph = $derived<ConceptGraphOut | null>(data.graph);
  let notFound = $derived<boolean>(data.reason === 'not_found');
  let error = $state<string | null>(null);

  /** Post-write refetch (promote from the Time Machine). */
  function load(conceptId: string, reset = true): void {
    if (reset) graph = null;
    error = null;
    api
      .graph(conceptId)
      .then((g) => (graph = g))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) notFound = true;
        else error = errorMessage(e);
      });
    loadActivity(conceptId);
  }

  $effect(() => {
    if (data.graph === null && data.reason === null) {
      // SSR saw 404 with a login signal — retry with the real session.
      load(id);
    }
  });

  const latestVersion = $derived(graph ? (graph.versions[graph.versions.length - 1] ?? null) : null);
  const latestName = $derived(latestVersion?.canonical_form ?? '');

  // ── Activity list ↔ Time Machine two-way coupling ──
  // night4.* is browser-only (no serverApi surface), so the feed is fetched
  // client-side rather than from +page.ts's SSR load.
  let activity = $state<ActivityItem[]>([]);

  function loadActivity(conceptId: string): void {
    night4
      .conceptActivity(conceptId, 100)
      .then((items) => (activity = items))
      .catch(() => {
        /* supplementary feed — an empty list falls back to ActivityList's own
         * "no events yet" state, no separate error UI needed here. */
      });
  }

  $effect(() => {
    if (id) loadActivity(id);
  });

  /** `?v=<version_id>` deep link — read once; TimeMachine applies it once too. */
  const initialVersionId = $derived(page.url.searchParams.get('v'));

  /** Player → list highlight (updated by TimeMachine's onversionchange). */
  let currentVersionId = $state<string | null>(null);

  /** List → player seek: rows with a version_id seek directly; rows without
   * one (a concept-level comment/proposal) seek to the latest version at/
   * before the row's date — TimeMachine pauses first, which is exactly the
   * "paused → expanded pocket" state the anti-flutter design calls for. */
  let seekRequest = $state<{ versionId?: string | null; before?: string | null } | null>(null);

  function jumpToActivity(item: ActivityItem): void {
    seekRequest = item.version_id ? { versionId: item.version_id } : { before: item.at };
  }
</script>

<svelte:head>
  <title>{t('hist.head_title', { name: latestName })}</title>
  {#if latestVersion}
    <meta name="description" content={stripMarkdown(latestVersion.definition_md).slice(0, 160)} />
  {/if}
</svelte:head>

<div class="container">
  <nav class="ui breadcrumb">
    <a href="/concepts/{id}">{t('hist.back')}</a>
  </nav>

  <h1 class="hist-h1">{t('hist.h1')}</h1>

  {#if error}
    <p class="ui">{t('hist.error', { error })}</p>
  {:else if notFound || data.reason === 'error'}
    <EmptyState
      icon="clock"
      heading={data.reason === 'error' ? t('soft404.load_error_h') : t('soft404.concept_h')}
      body={data.reason === 'error' ? t('soft404.load_error_body') : t('soft404.concept_body')}
    >
      {#snippet actions()}
        <a class="btn-primary" href="/">{t('soft404.search_concepts')}</a>
        <a class="btn" href="/collections">{t('soft404.to_collections')}</a>
      {/snippet}
    </EmptyState>
  {:else if graph}
    {#key graph.concept_id}
      <TimeMachine
        {graph}
        {activity}
        {initialVersionId}
        {seekRequest}
        onchanged={() => load(id, false)}
        onversionchange={(versionId) => (currentVersionId = versionId)}
      />
    {/key}

    <section class="activity-section">
      <h2>{t('hist.activity_h2')}</h2>
      <ActivityList items={activity} highlightVersionId={currentVersionId} onselect={jumpToActivity} />
    </section>
  {:else}
    <p class="ui loading">{t('hist.loading')}</p>
  {/if}
</div>

<style>

  .hist-h1 {
    margin-bottom: var(--space-4);
  }

  .loading {
    color: var(--ink-3);
  }

  .activity-section {
    margin-top: var(--space-8);
  }
</style>
