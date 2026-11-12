<script lang="ts">
  import { untrack } from 'svelte';
  import { page } from '$app/state';
  import {
    api,
    ApiError,
    type CollectionEditPayload,
    type CollectionOut,
    type ConceptListItem
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import ConceptCard from '$lib/components/ConceptCard.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import InfiniteSentinel from '$lib/components/InfiniteSentinel.svelte';
  import { hasMore, PAGE_LIMIT } from '$lib/components/infiniteList';
  import { ConceptBrowser } from '$lib/components/conceptBrowser.svelte';
  import { EXPORT_FORMATS } from '$lib/exports/formats';
  import SearchBar from '$lib/search/SearchBar.svelte';
  import { type SearchFilterState } from '$lib/search/SearchFilters.svelte';
  import CollectionTaxonomies from '$lib/taxonomy/CollectionTaxonomies.svelte';
  import { localizedCollection } from '$lib/collections/locale';
  import { formatNumber, i18n, t } from '$lib/i18n.svelte';
  import { renderMarkdown } from '$lib/text';
  import { adminOrgs, currentUser, isOrgAdmin } from '$lib/user.svelte';
  import type { PageProps, Snapshot } from './$types';

  let { data }: PageProps = $props();

  const slug = $derived(page.params.slug ?? '');

  // Writable deriveds: render the load seed (SSR included); client fetches
  // and writes assign overrides, and navigations reset them to fresh data.
  let collection = $derived<CollectionOut | null>(data.collection);
  // Soft not-found (paket D): from the load seed, or from a failed client
  // retry — rendered as an informative in-page state, never an error page.
  let notFound = $derived<boolean>(data.reason === 'not_found');
  // Locale-aware name / short / rich description (migration 007), reactive to
  // the UI language with graceful fallback to the other language.
  const loc = $derived(collection ? localizedCollection(collection, i18n.lang) : null);
  let q = $state('');
  // The SAME filter system as the main search, prescoped to this collection
  // (Bengt deep-review: one filter implementation; OR within a type).
  let filters = $state<SearchFilterState>({
    language: '',
    categories: [],
    collections: [],
    tags: [],
    statuses: []
  });
  const filterKey = (f: SearchFilterState): string =>
    JSON.stringify([f.language, f.categories, f.tags, f.statuses]);
  /** The zero-hit state's secondary action: back to the full collection. */
  function clearSearch(): void {
    q = '';
    filters = { language: '', categories: [], collections: [], tags: [], statuses: [] };
  }
  // Accumulating concept list (infinite scroll), seeded from the load data
  // so the first page still renders server-side (SEO). The seed is captured
  // once by design — later `data` changes (client-side navigation between
  // collections) are handled by the query effect below via key mismatch.
  // svelte-ignore state_referenced_locally
  const initialSeed = data.concepts;
  type ActiveQuery = { slug: string; q: string; filters: SearchFilterState };
  // The shared browse engine (conceptBrowser.svelte.ts) owns the accumulating list.
  const browser = new ConceptBrowser<ActiveQuery>({
    fetchPage: (params, offset, limit) =>
      api.concepts({
        collection: params.slug,
        q: params.q || undefined,
        language: params.filters.language || undefined,
        category: params.filters.categories.join(',') || undefined,
        tag: params.filters.tags.join(',') || undefined,
        status: params.filters.statuses.join(',') || undefined,
        limit,
        offset
      }),
    sameParams: (a, b) =>
      a.slug === b.slug && a.q === b.q && filterKey(a.filters) === filterKey(b.filters),
    seed: initialSeed
      ? {
          params: {
            slug: page.params.slug ?? '',
            q: '',
            filters: { language: '', categories: [], collections: [], tags: [], statuses: [] }
          },
          page: initialSeed
        }
      : null
  });

  // Position memory: capture the accumulated list when navigating to a
  // concept; restore() runs before render on history back, so the grid
  // re-renders at full height and the scroll position lands where the user
  // left.
  //
  // scrollY is hand-rolled: testing showed SvelteKit's native restoration is
  // insufficient here — with Svelte 5's batched DOM swap, kit reads the
  // outgoing scroll position after the (shorter) destination page is already
  // in the DOM, so the browser has clamped scrollY to that page's height
  // (e.g. leaving at 5000 restored to 2473 = destination height − viewport).
  // capture() runs while this page is still fully alive, so it sees the true
  // value; restore re-applies it one frame later, when the restored grid is
  // at full height.
  type CollectionSnapshot = {
    q: string;
    filters: SearchFilterState;
    list: ReturnType<ConceptBrowser<ActiveQuery>['capture']>;
    scrollY: number;
  };
  export const snapshot: Snapshot<CollectionSnapshot> = {
    capture: () => ({
      q,
      filters: $state.snapshot(filters),
      list: browser.capture(),
      scrollY: window.scrollY
    }),
    restore: (value) => {
      q = value.q;
      filters = value.filters;
      browser.restore(value.list);
      requestAnimationFrame(() => scrollTo(0, value.scrollY));
    }
  };

  // The restore flag only applies to the sentinel mounted in the first
  // render — later sentinel re-creations (filter change) must not skip.
  $effect(() => {
    browser.restoredFromSnapshot = false;
  });

  const STATUS_OPTIONS = $derived([
    { value: '', label: t('coll.status_all') },
    { value: 'draft', label: t('coll.status_draft_pl') },
    { value: 'proposed', label: t('coll.status_proposed_pl') },
    { value: 'endorsed', label: t('coll.status_endorsed_pl') },
    { value: 'deprecated', label: t('coll.status_deprecated_pl') },
    { value: 'superseded', label: t('coll.status_superseded_pl') }
  ]);


  // Redigera samlingen (inline form)
  let editing = $state(false);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let dName = $state('');
  let dDescription = $state('');
  let dYear = $state<number | null>(null);
  let dLicenceLabel = $state('');
  let dLicenceUrl = $state('');
  let dVisibility = $state<'public' | 'org_private' | 'private'>('public');
  let dPolicy = $state<'org' | 'anyone'>('anyone');
  let dOrgId = $state('');
  let dAuthoritative = $state(false);
  let dCredits = $state('');
  let dSourceUrl = $state('');
  let dArchiveUrl = $state('');

  const licenceLabel = $derived((collection?.licence?.label as string | undefined) ?? null);
  const licenceUrl = $derived((collection?.licence?.url as string | undefined) ?? null);

  // A null seed means SSR saw 404 with a login signal — retry here with the
  // real session (this effect only runs in the browser). A retry that still
  // 404s lands in the soft not-found state below.
  $effect(() => {
    if (data.collection === null && data.reason === null) {
      api
        .collection(slug)
        .then((c) => (collection = c))
        .catch((e) => {
          if (e instanceof ApiError && e.status === 404) notFound = true;
        });
    }
  });

  $effect(() => {
    const s = slug;
    const query = q.trim();
    const f = $state.snapshot(filters) as SearchFilterState;
    const seed = data.concepts;
    untrack(() => {
      const next: ActiveQuery = { slug: s, q: query, filters: f };
      // Default filters render the load-seeded first page — no duplicate
      // fetch on hydration. Any filter interaction resets and refetches.
      const emptyKey = filterKey({
        language: '',
        categories: [],
        collections: [],
        tags: [],
        statuses: []
      });
      const isDefault = !query && filterKey(f) === emptyKey && !!seed;
      browser.reset(next, {
        immediate: isDefault ? seed : null,
        debounceMs: query ? 220 : 0
      });
    });
  });

  // Lock & archive (iteration 3) — server enforces; UI mirrors the rights.
  type CollToggle = 'lock' | 'unlock' | 'archive' | 'unarchive';
  let togglePending = $state<CollToggle | null>(null);
  let toggleBusy = $state(false);
  let toggleError = $state<string | null>(null);

  const TOGGLE_TEXTS: Record<CollToggle, { explain: string; confirmLabel: string }> = $derived({
    lock: { explain: t('coll.lock_explain'), confirmLabel: t('coll.lock_confirm') },
    unlock: { explain: t('coll.unlock_explain'), confirmLabel: t('coll.unlock_confirm') },
    archive: { explain: t('coll.archive_explain'), confirmLabel: t('coll.archive_confirm') },
    unarchive: { explain: t('coll.unarchive_explain'), confirmLabel: t('coll.unarchive_confirm') }
  });

  const managesCollection = $derived(
    currentUser.is_super_admin ||
      (!!collection?.organisation && isOrgAdmin(collection.organisation.id))
  );
  const isArchived = $derived(collection?.is_archived === true);
  const isLocked = $derived(collection?.is_locked === true);
  const writeBlocked = $derived(isArchived || (isLocked && !managesCollection));
  const blockedTitle = $derived(
    isArchived ? t('coll.blocked_archived') : t('coll.blocked_locked')
  );

  function requestToggle(toggle: CollToggle): void {
    togglePending = toggle;
    toggleError = null;
  }

  // Exportera-menyn i verktygsraden (speglar begreppssidans Hantera-popover).
  let exportOpen = $state(false);
  let exportTrigger = $state<HTMLButtonElement | undefined>();

  $effect(() => {
    if (!exportOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        exportOpen = false;
        exportTrigger?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.export-wrap')) exportOpen = false;
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onClick);
    };
  });

  async function applyToggle(): Promise<void> {
    if (!togglePending || !collection || toggleBusy) return;
    const toggle = togglePending;
    toggleBusy = true;
    toggleError = null;
    const payload: CollectionEditPayload =
      toggle === 'lock' || toggle === 'unlock'
        ? { is_locked: toggle === 'lock' }
        : { is_archived: toggle === 'archive' };
    try {
      collection = await api.patchCollection(slug, payload);
      togglePending = null;
    } catch (e) {
      toggleError = errorMessage(e);
    } finally {
      toggleBusy = false;
    }
  }

  function startEdit(): void {
    if (!collection) return;
    dName = collection.name;
    dDescription = collection.description ?? '';
    dYear = collection.year ?? null;
    dLicenceLabel = (collection.licence?.label as string | undefined) ?? '';
    dLicenceUrl = (collection.licence?.url as string | undefined) ?? '';
    dVisibility = collection.visibility ?? 'public';
    dPolicy =
      collection.edit_policy === 'org' ? 'org' : 'anyone';
    dOrgId = collection.organisation?.id ?? '';
    dAuthoritative = collection.authoritative;
    dCredits = collection.credits ?? '';
    dSourceUrl = collection.source_url ?? '';
    dArchiveUrl = collection.archive_url ?? '';
    saveError = null;
    editing = true;
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!collection) return;
    saveError = null;
    if (!dName.trim()) {
      saveError = t('coll.save_error_name');
      return;
    }
    const payload: CollectionEditPayload = {
      name: dName.trim(),
      description: dDescription.trim() || null,
      year: typeof dYear === 'number' && !Number.isNaN(dYear) ? dYear : null,
      licence:
        dLicenceLabel.trim() || dLicenceUrl.trim()
          ? {
              ...(dLicenceLabel.trim() ? { label: dLicenceLabel.trim() } : {}),
              ...(dLicenceUrl.trim() ? { url: dLicenceUrl.trim() } : {})
            }
          : null,
      visibility: dVisibility,
      edit_policy: dPolicy,
      organisation_id: dOrgId || null,
      credits: dCredits.trim() || null,
      source_url: dSourceUrl.trim() || null,
      archive_url: dArchiveUrl.trim() || null
    };
    if (currentUser.is_super_admin) payload.authoritative = dAuthoritative;
    saving = true;
    try {
      collection = await api.patchCollection(slug, payload);
      editing = false;
    } catch (e) {
      saveError = errorMessage(e);
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>{loc?.name ?? collection?.name ?? t('coll.fallback_title')} {t('typo.dash')} Kollepedia NG</title>
  {#if loc?.short ?? collection?.description}
    <meta name="description" content={(loc?.short ?? collection?.description ?? '').slice(0, 160)} />
  {/if}
</svelte:head>

<div class="container">
  <nav class="ui breadcrumb"><a href="/collections">{t('coll.breadcrumb_all')}</a></nav>

  {#if collection}
    {#if isArchived}
      <p class="coll-banner archived ui" role="status">
        <span class="banner-icon" aria-hidden="true"><Icon name="archive" size={15} /></span>
        {t('coll.banner_archived')}
      </p>
    {:else if isLocked}
      <p class="coll-banner ui" role="status">
        <span class="banner-icon" aria-hidden="true"><Icon name="lock" filled size={15} /></span>
        {t('coll.banner_locked')}
      </p>
    {/if}

    <header class="head">
      <div class="head-row">
        <h1>{loc?.name ?? collection.name}</h1>
        <div class="head-actions ui">
          {#if writeBlocked}
            <span class="btn new-btn blocked" aria-disabled="true" title={blockedTitle}>
              {t('coll.new_concept')}
            </span>
          {:else}
            <a
              class="btn new-btn"
              href="/new-concept?collection={collection.slug}"
              title={t('coll.new_concept_title')}
            >
              {t('coll.new_concept')}
            </a>
          {/if}
        </div>
      </div>

      {#if editing}
        <form class="edit-form card ui" onsubmit={save} aria-label={t('coll.edit_form_aria')}>
          <div class="row">
            <div class="field grow">
              <label for="coll-name">{t('common.name')}</label>
              <input id="coll-name" class="input" type="text" bind:value={dName} disabled={saving} required />
            </div>
            <div class="field year">
              <label for="coll-year">{t('coll.year_label')}</label>
              <input
                id="coll-year"
                class="input"
                type="number"
                bind:value={dYear}
                disabled={saving}
                placeholder={t('coll.year_placeholder')}
              />
            </div>
          </div>
          <div class="field">
            <label for="coll-description">{t('coll.description_label')}</label>
            <textarea id="coll-description" class="input" rows="3" bind:value={dDescription} disabled={saving}
            ></textarea>
          </div>
          <div class="row">
            <div class="field grow">
              <label for="coll-licence-label">{t('coll.licence_label')}</label>
              <input
                id="coll-licence-label"
                class="input"
                type="text"
                bind:value={dLicenceLabel}
                disabled={saving}
                placeholder={t('coll.licence_placeholder')}
              />
            </div>
            <div class="field grow">
              <label for="coll-licence-url">{t('coll.licence_url_label')}</label>
              <input
                id="coll-licence-url"
                class="input"
                type="url"
                bind:value={dLicenceUrl}
                disabled={saving}
                placeholder="https://…"
              />
            </div>
          </div>
          <div class="row">
            <div class="field grow">
              <label for="coll-credits">{t('coll.credits_label')}</label>
              <input id="coll-credits" class="input" type="text" bind:value={dCredits} disabled={saving} />
            </div>
            <div class="field grow">
              <label for="coll-source-url">{t('coll.source_link')}</label>
              <input
                id="coll-source-url"
                class="input"
                type="url"
                bind:value={dSourceUrl}
                disabled={saving}
                placeholder="https://…"
              />
            </div>
            <div class="field grow">
              <label for="coll-archive-url">{t('coll.archive_link')}</label>
              <input
                id="coll-archive-url"
                class="input"
                type="url"
                bind:value={dArchiveUrl}
                disabled={saving}
                placeholder="https://web.archive.org/…"
              />
            </div>
          </div>
          <div class="row">
            <div class="field grow">
              <label for="coll-visibility">{t('coll.visibility_label')}</label>
              <select id="coll-visibility" class="input" bind:value={dVisibility} disabled={saving}>
                <option value="public">{t('coll.visibility_public_option')}</option>
                <option value="org_private">{t('coll.visibility_org_option')}</option>
                <option value="private">{t('coll.visibility_private_option')}</option>
              </select>
            </div>
            <div class="field grow">
              <label for="coll-policy">{t('coll.policy_label')}</label>
              <select id="coll-policy" class="input" bind:value={dPolicy} disabled={saving} title={t('coll.policy_hint')}>
                <option value="org">{t('coll.policy_org')}</option>
                <option value="anyone">{t('coll.policy_anyone')}</option>
              </select>
            </div>
            <div class="field grow">
              <label for="coll-org">{t('coll.org_label')}</label>
              <select id="coll-org" class="input" bind:value={dOrgId} disabled={saving}>
                <option value="">{t('coll.no_org')}</option>
                {#if collection.organisation}
                  <option value={collection.organisation.id}>{collection.organisation.name}</option>
                {/if}
                {#each adminOrgs().filter((o) => o.id !== collection?.organisation?.id) as org (org.id)}
                  <option value={org.id}>{org.name}</option>
                {/each}
              </select>
            </div>
          </div>
          {#if currentUser.is_super_admin}
            <div class="field checkline">
              <label class="check" for="coll-authoritative">
                <input
                  id="coll-authoritative"
                  type="checkbox"
                  bind:checked={dAuthoritative}
                  disabled={saving}
                />
                {t('coll.authoritative_check')}
              </label>
            </div>
          {/if}
          {#if saveError}
            <p class="error" role="alert">{saveError}</p>
          {/if}
          <div class="actions">
            <button type="submit" class="btn btn-primary" disabled={saving}>
              {saving ? t('common.saving') : t('common.save')}
            </button>
            <button type="button" class="btn btn-quiet" onclick={() => (editing = false)}>
              {t('common.cancel')}
            </button>
          </div>
        </form>

        {#if managesCollection}
          <CollectionTaxonomies {collection} />
        {/if}
      {:else}
        {#if loc?.short ?? collection.description}
          <p class="desc">{loc?.short ?? collection.description}</p>
        {/if}

        {#if loc?.description}
          <section class="about" aria-label={t('coll.about_heading')}>
            <h2>{t('coll.about_heading')}</h2>
            {#if loc.descriptionLang && loc.descriptionLang !== i18n.lang}
              <p class="lang-note ui" role="note">
                {loc.descriptionLang === 'sv'
                  ? t('coll.desc_other_lang_sv')
                  : t('coll.desc_other_lang_en')}
              </p>
            {/if}
            <!-- eslint-disable-next-line svelte/no-at-html-tags — trusted authored markdown recovered by migration 007 -->
            <div class="prose">{@html renderMarkdown(loc.description)}</div>
            {#if collection.credits || collection.source_url || collection.archive_url}
              <ul class="provenance ui">
                {#if collection.credits}
                  <li><span class="prov-label">{t('coll.credits_label')}:</span> {collection.credits}</li>
                {/if}
                {#if collection.source_url}
                  <li>
                    <a href={collection.source_url} target="_blank" rel="noopener noreferrer"
                      >{t('coll.source_link')}</a
                    >
                  </li>
                {/if}
                {#if collection.archive_url}
                  <li>
                    <a href={collection.archive_url} target="_blank" rel="noopener noreferrer"
                      >{t('coll.archive_link')}</a
                    >
                  </li>
                {/if}
              </ul>
            {/if}
          </section>
        {/if}

        <dl class="ui metadata">
          {#if collection.year}
            <div><dt>{t('coll.year_label')}</dt><dd>{collection.year}</dd></div>
          {/if}
          <div>
            <dt>{t('coll.meta_concepts')}</dt>
            <dd>{formatNumber(collection.concept_count)}</dd>
          </div>
          <div>
            <dt>{t('coll.licence_label')}</dt>
            <dd>
              {#if licenceUrl}
                <a href={licenceUrl} target="_blank" rel="noopener noreferrer"
                  >{licenceLabel ?? licenceUrl}</a
                >
              {:else if licenceLabel}
                {licenceLabel}
              {:else}
                {t('typo.dash')}
              {/if}
            </dd>
          </div>
          <div>
            <dt>{t('coll.visibility_label')}</dt>
            <dd>
              {(collection.visibility ?? 'public') === 'org_private'
                ? t('coll.visibility_org_value')
                : collection.visibility === 'private'
                  ? t('coll.visibility_private_value')
                  : t('coll.visibility_public_value')}
            </dd>
          </div>
          {#if collection.edit_policy}
            <div>
              <dt>{t('coll.policy_label')}</dt>
              <dd>
                {collection.edit_policy === 'org' ? t('coll.policy_org') : t('coll.policy_anyone')}
              </dd>
            </div>
          {/if}
          {#if collection.organisation}
            <div><dt>{t('coll.org_label')}</dt><dd>{collection.organisation.name}</dd></div>
          {/if}
          {#if collection.created_by}
            <div><dt>{t('coll.created_by')}</dt><dd class="mono">{collection.created_by}</dd></div>
          {/if}
          {#if collection.authoritative}
            <div><dt>{t('common.status')}</dt><dd>{t('coll.authoritative_value')}</dd></div>
          {/if}
        </dl>

        <!-- Verktygsraden — begreppssidans mönster (beslut 2026-07-16):
             Skrivskydda · Redigera · Exportera · Importera, under metainfo,
             ovanför Författare. Nytt begrepp bor kvar i sidhuvudet. -->
        <div class="tool-row ui" role="group" aria-label={t('coll.tools_aria')}>
          {#if collection.editable}
            <button
              type="button"
              class="btn tool-btn"
              class:active={isLocked}
              disabled={toggleBusy}
              aria-pressed={isLocked}
              onclick={() => requestToggle(isLocked ? 'unlock' : 'lock')}
              title={isLocked ? t('coll.unlock_title') : t('coll.lock_title')}
            >
              <Icon name="lock" filled={isLocked} />
              {isLocked ? t('coll.unlock_btn') : t('coll.lock_btn')}
            </button>
            <button type="button" class="btn tool-btn" onclick={startEdit}>
              <Icon name="edit" />
              {t('coll.edit_btn')}
            </button>
          {/if}
          {#if collection.export_allowed === false}
            <!-- Published by permission without redistribution rights: readable
                 here, never handed out as a file (server returns 403 too). -->
            <span class="ui small export-blocked">
              <Icon name="download" />
              {t('coll.export_blocked')}
            </span>
          {:else}
            <span class="export-wrap">
              <button
                type="button"
                class="btn tool-btn"
                class:active={exportOpen}
                aria-haspopup="menu"
                aria-expanded={exportOpen}
                onclick={() => (exportOpen = !exportOpen)}
                bind:this={exportTrigger}
              >
                <Icon name="download" />
                {t('coll.export_label')}
              </button>
              {#if exportOpen}
                <div class="export-menu card ui" role="menu" aria-label={t('coll.export_label')}>
                  {#each EXPORT_FORMATS as { format, label } (format)}
                    <a
                      role="menuitem"
                      href={api.exportUrl('collections', collection.slug, format)}
                      onclick={() => (exportOpen = false)}
                    >
                      {label}
                    </a>
                  {/each}
                </div>
              {/if}
            </span>
          {/if}
          {#if collection.can_write}
            {#if writeBlocked}
              <span class="btn tool-btn blocked" aria-disabled="true" title={blockedTitle}>
                <Icon name="upload" />
                {t('coll.import_link')}
              </span>
            {:else}
              <a class="btn tool-btn" href="/collections/{collection.slug}/import">
                <Icon name="upload" />
                {t('coll.import_link')}
              </a>
            {/if}
          {/if}
        </div>

        {#if collection.editable && togglePending}
          <div class="toggle-confirm card ui" role="alert">
            <p>{TOGGLE_TEXTS[togglePending].explain}</p>
            {#if toggleError}
              <p class="error" role="alert">{toggleError}</p>
            {/if}
            <div class="actions">
              <button type="button" class="btn btn-primary" disabled={toggleBusy} onclick={applyToggle}>
                {toggleBusy ? t('common.saving') : TOGGLE_TEXTS[togglePending].confirmLabel}
              </button>
              <button type="button" class="btn btn-quiet" disabled={toggleBusy} onclick={() => (togglePending = null)}>
                {t('common.cancel')}
              </button>
            </div>
          </div>
        {/if}

        {#if collection.contributors?.length}
          <!-- Paket B: the living author list — v1's Ordbok publication credit,
               now computed for every collection and linked to author pages. -->
          <section class="contributors" aria-labelledby="contributors-h">
            <h2 id="contributors-h">{t('coll.contributors_h')}</h2>
            <ul class="contributors-list ui">
              {#each collection.contributors as contributor (contributor.handle)}
                <li>
                  <a class="contributor-name" href="/authors/{contributor.handle}"
                    >{contributor.display_name}</a
                  >
                  {#if !contributor.activated}
                    <span class="pill historic" title={t('authors.historic_title')}
                      >{t('authors.historic')}</span
                    >
                  {/if}
                  {#if contributor.affiliation}
                    <span class="contributor-affiliation">{contributor.affiliation}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          </section>
        {/if}

        {#if collection.editable}
          <!-- Lås-toggeln bor bredvid "Redigera" i sidhuvudet (2026-07-15);
               här ligger bara arkivering. Bekräftelsen för båda renderas
               inline högst upp intill toggeln. -->
          <div class="manage ui" role="group" aria-label={t('coll.manage_aria')}>
            <span class="tools-label">{t('coll.manage_label')}</span>
            <button
              type="button"
              class="btn btn-quiet"
              disabled={toggleBusy}
              onclick={() => requestToggle(isArchived ? 'unarchive' : 'archive')}
              title={isArchived ? t('coll.unarchive_title') : t('coll.archive_title')}
            >
              {isArchived ? t('coll.unarchive_btn') : t('coll.archive_btn')}
            </button>
          </div>
        {/if}
      {/if}
    </header>

    <SearchBar
      bind:q
      {filters}
      scopedCollection={slug}
      placeholder={t('coll.search_placeholder')}
      ariaLabel={t('coll.search_aria')}
      onchange={(next) => (filters = next)}
    />

    <div class="card-grid">
      {#each browser.items as concept (concept.id)}
        <ConceptCard {concept} />
      {/each}
    </div>

    {#if browser.total !== null && browser.items.length === 0}
      <!-- Zero-hit path forward (paket D2): the create chip appears ONLY at
           exactly zero hits (never on partial results) and only for signed-in
           users in a writable collection. -->
      <EmptyState
        icon="search"
        heading={t('empty.no_hits_h')}
        body={q.trim() ? t('empty.no_hits_for', { query: q.trim() }) : t('coll.no_match')}
      >
        {#snippet actions()}
          {#if q.trim() && currentUser.handle && !writeBlocked}
            <a
              class="btn-primary"
              href="/new-concept?collection={collection?.slug ?? ''}&name={encodeURIComponent(q.trim())}"
              data-testid="create-from-search"
            >
              {t('empty.create_from_search', { query: q.trim() })}
            </a>
          {/if}
          <button type="button" class="btn" onclick={clearSearch}>
            {t('empty.clear_filters')}
          </button>
        {/snippet}
      </EmptyState>
    {/if}

    {#if browser.total !== null && browser.total > 0}
      <InfiniteSentinel
        count={browser.items.length}
        total={browser.total}
        loading={browser.loadingMore}
        hasMore={hasMore(browser.offset, browser.total)}
        skipFirst={browser.restoredFromSnapshot}
        onLoadMore={() => browser.loadMore()}
      />
    {/if}
  {:else if notFound || data.reason === 'error'}
    <EmptyState
      icon="book"
      heading={data.reason === 'error' ? t('soft404.load_error_h') : t('soft404.collection_h')}
      body={data.reason === 'error'
        ? t('soft404.load_error_body')
        : currentUser.handle
          ? t('soft404.collection_body')
          : `${t('soft404.collection_body')} ${t('soft404.login_hint')}`}
      level={1}
    >
      {#snippet actions()}
        <a class="btn-primary" href="/collections">{t('soft404.to_collections')}</a>
        <a class="btn" href="/">{t('soft404.search_concepts')}</a>
      {/snippet}
    </EmptyState>
  {:else}
    <p class="empty ui">{t('common.searching')}</p>
  {/if}
</div>

<style>


  .head-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .head-actions {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .new-btn {
    text-decoration: none;
    white-space: nowrap;
  }

  .blocked {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .contributors {
    margin: var(--space-8) 0;
  }

  .contributors h2 {
    margin-bottom: var(--space-3);
  }

  .contributors-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: var(--space-2) var(--space-6);
    font-size: var(--text-sm);
  }

  .contributor-name {
    color: var(--ink);
    text-decoration: none;
    border-bottom: 1px solid var(--line);
  }

  .contributor-name:hover {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .contributor-affiliation {
    color: var(--ink-3);
    margin-left: var(--space-2);
  }

  .historic {
    border-style: dashed;
    border-color: var(--line-strong);
    color: var(--ink-3);
    margin-left: var(--space-1);
  }

  span.new-btn.blocked:hover {
    background: transparent;
    color: var(--ink);
  }

  .coll-banner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-6);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--endorsed);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--endorsed) 9%, transparent);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .banner-icon {
    display: inline-flex;
    flex-shrink: 0;
    color: var(--endorsed);
  }

  .coll-banner.archived {
    border-color: var(--del-strong);
    background: var(--del-wash);
  }

  .manage {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: var(--space-3);
  }

  .toggle-confirm {
    max-width: 65ch;
    margin-top: var(--space-3);
    padding: var(--space-4);
    font-size: var(--text-sm);
  }

  .toggle-confirm p {
    margin: 0 0 var(--space-3);
    color: var(--ink-2);
  }

  .desc {
    max-width: 70ch;
    color: var(--ink-2);
    margin: var(--space-2) 0 var(--space-3);
  }

  /* ── Rich "About" (migration 007 locale description) ── */
  .about {
    max-width: 72ch;
    margin: var(--space-4) 0 var(--space-6);
    padding: var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
  }

  .about > h2 {
    margin-bottom: var(--space-3);
  }

  .lang-note {
    font-size: var(--text-sm);
    color: var(--ink-3);
    border-left: 3px solid var(--accent);
    padding: var(--space-1) var(--space-3);
    margin-bottom: var(--space-3);
  }

  /* Injected by {@html renderMarkdown(...)} — :global reaches the nodes. */
  .prose {
    font-size: var(--text-base);
    line-height: 1.7;
    color: var(--ink-2);
  }

  .prose :global(h2) {
    font-size: var(--text-base);
    font-weight: 640;
    color: var(--ink);
    margin: var(--space-6) 0 var(--space-2);
  }

  .prose :global(h3) {
    font-size: var(--text-sm);
    font-weight: 640;
    color: var(--ink);
    margin: var(--space-4) 0 var(--space-2);
  }

  .prose :global(p) {
    margin: 0 0 var(--space-3);
  }

  .prose :global(ul),
  .prose :global(ol) {
    margin: 0 0 var(--space-3);
    padding-left: 1.4em;
  }

  .prose :global(a) {
    color: var(--accent);
  }

  .provenance {
    list-style: none;
    padding: 0;
    margin: var(--space-4) 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-6);
    font-size: var(--text-sm);
    border-top: 1px solid var(--line);
    padding-top: var(--space-3);
  }

  .prov-label {
    color: var(--ink-3);
  }

  .provenance a {
    color: var(--accent);
    text-decoration: none;
  }

  .provenance a:hover {
    text-decoration: underline;
  }

  .metadata {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-6);
    margin: 0 0 var(--space-4);
  }

  .metadata div {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
  }

  .metadata dt {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .metadata dd {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--ink);
  }

  .metadata dd a {
    color: var(--accent);
  }

  .tools-label {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  /* Verktygsraden — begreppssidans tool-row-mönster. */
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
    text-decoration: none;
    white-space: nowrap;
  }

  .tool-btn.active {
    background: var(--ink);
    color: var(--bg);
    border-color: var(--ink);
  }

  span.tool-btn.blocked:hover {
    background: transparent;
    color: var(--ink);
  }

  .export-wrap {
    position: relative;
    display: inline-flex;
  }

  .export-blocked {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--ink-3);
  }

  .export-menu {
    position: absolute;
    z-index: 30;
    top: calc(100% + 6px);
    left: 0;
    min-width: 160px;
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
  }

  .export-menu a {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    color: var(--ink);
    font-size: var(--text-sm);
    text-align: left;
    text-decoration: none;
    border-radius: var(--radius-sm);
  }

  .export-menu a:hover,
  .export-menu a:focus-visible {
    background: var(--bg-sunken);
  }





  .empty {
    color: var(--ink-3);
    margin-top: var(--space-4);
  }

  .edit-form {
    margin-top: var(--space-4);
    padding: var(--space-6);
    max-width: 720px;
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
    min-width: 220px;
  }

  .year {
    width: 120px;
  }

  .edit-form label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .edit-form input:not([type='checkbox']),
  .edit-form textarea,
  .edit-form select {
    width: 100%;
  }

  .edit-form textarea {
    resize: vertical;
  }

  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    text-transform: none;
    letter-spacing: 0;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--ink);
    cursor: pointer;
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-3);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
  }





</style>
