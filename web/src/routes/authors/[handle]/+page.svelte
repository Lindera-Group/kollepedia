<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import { patchAdminUser } from '$lib/api';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  // Seeded by +page.ts (SSR + client navigations). An unknown or hidden
  // handle arrives as author=null + reason — rendered as a soft state
  // below, never an error page (paket D).
  const author = $derived(data.author);

  const collectionNames = $derived(author?.collections.map((c) => c.name).join(', ') ?? '');

  function roleLabel(role: string): string {
    if (role === 'admin') return t('orgs.role_admin');
    if (role === 'editor') return t('orgs.role_editor');
    if (role === 'viewer') return t('orgs.role_viewer');
    return role;
  }

  // Superadmin-moderering på författarsidan (beslut 4): suspendera kräver att
  // användarnamnet skrivs in (guardrail G4); återställning är enklicks.
  const canModerate = $derived(
    currentUser.is_super_admin && author && author.handle !== currentUser.handle
  );
  let moderationOpen = $state(false);
  let moderationTyped = $state('');
  let moderationBusy = $state(false);
  let moderationError = $state<string | null>(null);

  async function setActive(isActive: boolean): Promise<void> {
    if (!author) return;
    if (!isActive && moderationTyped.trim() !== author.handle) return;
    moderationBusy = true;
    moderationError = null;
    try {
      await patchAdminUser(author.id, { is_active: isActive });
      moderationOpen = false;
      moderationTyped = '';
      await invalidateAll();
    } catch (e) {
      moderationError = errorMessage(e);
    } finally {
      moderationBusy = false;
    }
  }

  /** Concepts grouped per collection, for a calmer reading order. */
  const groupedConcepts = $derived.by(() => {
    const groups = new Map<string, NonNullable<typeof author>['concepts']>();
    for (const concept of author?.concepts ?? []) {
      const list = groups.get(concept.collection_name) ?? [];
      list.push(concept);
      groups.set(concept.collection_name, list);
    }
    return [...groups.entries()];
  });
</script>

<svelte:head>
  <title>{author?.display_name ?? t('authd.fallback_title')} {t('typo.dash')} Kollepedia NG</title>
  {#if author}
    <meta
      name="description"
      content="{author.display_name}{author.affiliation ? ` (${author.affiliation})` : ''} {t('typo.dash')} {t(
        'authd.author_of'
      )} {author.concept_count} {t('common.concepts')}{collectionNames
        ? ` ${t('authd.in')} ${collectionNames}`
        : ''}."
    />
  {/if}
</svelte:head>

<div class="container">
  <nav class="ui breadcrumb"><a href="/authors">{t('authd.back')}</a></nav>

  {#if author}
    <article>
      <header class="head">
        <h1>{author.display_name}</h1>
        <div class="meta ui">
          {#if author.activated}
            <span class="pill st-activated" title={t('authors.activated_title')}
              >{t('authors.activated')}</span
            >
          {:else}
            <span class="pill st-historic" title={t('authors.historic_title')}
              >{t('authors.historic')}</span
            >
          {/if}
          <span class="pill mono">@{author.handle}</span>
          {#if !author.is_active}
            <span class="pill st-suspended">{t('authd.suspended_badge')}</span>
          {/if}
        </div>
        {#if author.memberships.length}
          <div class="memberships ui" aria-label={t('authd.memberships_label')}>
            {#each author.memberships as membership (membership.org_slug + (membership.ended_at ?? ''))}
              <span class="pill" class:ended={membership.ended_at !== null}>
                {membership.org_name} · {roleLabel(membership.role)}{#if membership.kind === 'guest'}
                  · {t('orgs.kind_guest')}{/if}{#if !membership.is_public}
                  · {t('authd.membership_hidden')}{/if}{#if membership.ended_at}
                  · {t('authd.membership_ended', { date: formatDate(membership.ended_at) })}{/if}
              </span>
            {/each}
          </div>
        {/if}
        {#if author.affiliation}
          <p class="affiliation">{author.affiliation}</p>
        {/if}
        {#if author.bio}
          <p class="bio">{author.bio}</p>
        {/if}
        {#if author.web_url}
          <p class="ui weblink">
            <a href={author.web_url} target="_blank" rel="noopener noreferrer"
              >{t('sections.external_profile')} <span aria-hidden="true">↗</span></a
            >
          </p>
        {/if}
      </header>

      <div class="prov card ui">
        <p>
          {t('authd.author_of')} <strong>{author.concept_count} {t('common.concepts')}</strong>
          {#if author.section_count > 0}
            {t('authd.of_which')} {author.section_count}
            {author.section_count === 1 ? t('authd.def_section_singular') : t('authd.def_sections')}
          {/if}
          {#if collectionNames}
            {t('authd.in')} {collectionNames}.{:else}.{/if}
        </p>
        {#if author.version_count > 0}
          <p class="mono versions">
            {author.version_count}
            {author.version_count === 1 ? t('authd.version_authored_singular') : t('authd.versions_authored')}
          </p>
        {/if}
        {#if !author.activated}
          <p class="activate-hint">
            {t('authd.is_this_you')} <a href="/activate?handle={author.handle}"
              >{t('authd.activate_link')}</a
            > {t('authd.activate_rest')}
          </p>
        {/if}
      </div>

      {#if canModerate}
        <div class="moderation card ui" aria-label={t('authd.moderation_aria')}>
          {#if author.is_active}
            {#if moderationOpen}
              <p class="mod-confirm" role="alert">
                {t('authd.moderation_confirm', { handle: author.handle })}
              </p>
              <div class="mod-row">
                <input
                  type="text"
                  class="input mono mod-input"
                  bind:value={moderationTyped}
                  placeholder={author.handle}
                  spellcheck="false"
                  aria-label={t('authd.moderation_confirm', { handle: author.handle })}
                />
                <button
                  type="button"
                  class="btn-danger"
                  disabled={moderationBusy || moderationTyped.trim() !== author.handle}
                  onclick={() => setActive(false)}
                >
                  {moderationBusy ? t('common.saving') : t('authd.moderation_suspend')}
                </button>
                <button
                  type="button"
                  class="btn btn-quiet"
                  disabled={moderationBusy}
                  onclick={() => {
                    moderationOpen = false;
                    moderationTyped = '';
                    moderationError = null;
                  }}
                >
                  {t('common.cancel')}
                </button>
              </div>
            {:else}
              <button
                type="button"
                class="btn-danger"
                onclick={() => (moderationOpen = true)}
              >
                {t('authd.moderation_suspend')}
              </button>
            {/if}
          {:else}
            <button
              type="button"
              class="btn btn-quiet"
              disabled={moderationBusy}
              onclick={() => setActive(true)}
            >
              {moderationBusy ? t('common.saving') : t('authd.moderation_restore')}
            </button>
          {/if}
          {#if moderationError}
            <p class="mod-error" role="alert">{moderationError}</p>
          {/if}
        </div>
      {/if}

      {#if groupedConcepts.length}
        <section class="concepts">
          <h2>{t('authd.concepts_h2')}</h2>
          {#each groupedConcepts as [collectionName, concepts] (collectionName)}
            <h3 class="ui coll-head">{collectionName}</h3>
            <ul>
              {#each concepts as concept (concept.id)}
                <li><a href="/concepts/{concept.id}">{concept.canonical_form}</a></li>
              {/each}
            </ul>
          {/each}
          {#if author.concepts.length >= 100}
            <p class="ui truncated">{t('authd.truncated')}</p>
          {/if}
        </section>
      {/if}
    </article>
  {:else if data.reason === 'error'}
    <EmptyState icon="person" heading={t('authd.loaderr_h')} body={t('authd.loaderr_body')} level={1}>
      {#snippet actions()}
        <a class="btn" href="/authors">{t('authd.notfound_link')}</a>
      {/snippet}
    </EmptyState>
  {:else}
    <EmptyState icon="person" heading={t('authd.noprofile_h')} level={1}>
      <p>
        {t('authd.noprofile_1')} <span class="mono">@{data.handle}</span>
        {t('authd.noprofile_2')}
      </p>
      {#snippet actions()}
        <a class="btn-primary" href="/authors">{t('authd.notfound_link')}</a>
        <a class="btn" href="/">{t('errpage.home_link')}</a>
      {/snippet}
    </EmptyState>
  {/if}
</div>

<style>

  .head h1 {
    margin-bottom: var(--space-3);
  }

  .meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }

  .st-activated {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .st-historic {
    border-style: dashed;
    border-color: var(--line-strong);
    color: var(--ink-3);
  }

  .st-suspended {
    border-color: var(--del-strong);
    color: var(--del-strong);
  }

  .memberships {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .memberships .ended {
    opacity: 0.6;
    text-decoration: line-through;
  }

  .moderation {
    max-width: 65ch;
    margin: var(--space-4) 0;
    font-size: var(--text-sm);
  }

  .mod-confirm {
    margin: 0 0 var(--space-2);
    color: var(--ink-2);
    font-size: var(--text-xs);
  }

  .mod-row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }

  /* Compact confirm-row flavour of .input; restores the .mono look that the
     later-defined .input primitive would otherwise override. */
  .mod-input {
    width: 16ch;
    padding: var(--space-1) var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .mod-error {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  .bio {
    color: var(--ink-2);
    max-width: 60ch;
    line-height: 1.6;
    margin: var(--space-2) 0 0;
  }

  .affiliation {
    font-size: var(--text-lg);
    color: var(--ink-2);
    margin: 0 0 var(--space-2);
    max-width: 60ch;
  }

  .weblink {
    font-size: var(--text-sm);
    margin: 0;
  }

  .prov {
    max-width: 65ch;
    margin: var(--space-6) 0;
    font-size: var(--text-sm);
  }

  .prov p {
    margin: 0 0 var(--space-2);
  }

  .prov p:last-child {
    margin-bottom: 0;
  }

  .versions {
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .activate-hint {
    padding-top: var(--space-2);
    border-top: 1px dashed var(--line);
    color: var(--ink-2);
  }

  .concepts {
    margin: var(--space-8) 0;
  }

  .concepts h2 {
    margin-bottom: var(--space-3);
  }

  .coll-head {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: var(--space-4) 0 var(--space-2);
  }

  .concepts ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-1) var(--space-4);
  }

  .truncated {
    margin-top: var(--space-3);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }
</style>
