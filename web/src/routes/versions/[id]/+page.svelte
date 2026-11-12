<script lang="ts">
  /** Citable version permalink (VISION §10 pillar) — the frozen version
   * rendered in full, with a Citera box (permanent URL + ready citation
   * line) and links back to the concept and its Time Machine. */
  import Icon from '$lib/icons/Icon.svelte';
  import CollectionBadge from '$lib/components/CollectionBadge.svelte';
  import { page } from '$app/state';
  import { ApiError, night4, type VersionPermalinkOut } from '$lib/api';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { errorMessage } from '$lib/errors';
  import { formatDate, languageLabel, statusLabel, t } from '$lib/i18n.svelte';
  import { formatCitation, shortId } from '$lib/proposals/cite';
  import { renderMarkdown, stripMarkdown } from '$lib/text';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  const id = $derived(page.params.id ?? '');

  // Writable derived: renders the load seed (SSR included); the org-private
  // client retry assigns an override, and navigations reset it. A hard
  // not-found is a soft in-page state (paket D), never an error page.
  let version = $derived<VersionPermalinkOut | null>(data.version);
  let notFound = $derived<boolean>(data.reason === 'not_found');
  let error = $state<string | null>(null);
  let copied = $state<'url' | 'cite' | null>(null);
  let copyTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const versionId = id;
    const seeded = data.version; // tracked: re-runs on client navigations
    error = null;
    copied = null;
    if (!seeded && data.reason === null) {
      // SSR saw 404 with a login signal — retry with the real session.
      night4
        .version(versionId)
        .then((v) => (version = v))
        .catch((e) => {
          if (e instanceof ApiError && e.status === 404) notFound = true;
          else error = errorMessage(e);
        });
    }
    return () => clearTimeout(copyTimer);
  });

  // page.url.origin (not location.origin) — this line renders server-side.
  const permUrl = $derived(version ? `${page.url.origin}/versions/${version.id}` : '');
  const citation = $derived(
    version
      ? formatCitation({
          author: version.created_by?.display_name ?? t('tm.unknown_author'),
          dash: t('typo.dash'),
          canonicalForm: version.canonical_form,
          collection: version.collection.name,
          versionId: version.id,
          date: formatDate(version.created_at),
          url: permUrl
        })
      : ''
  );

  async function copy(text: string, which: 'url' | 'cite'): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      copied = which;
      clearTimeout(copyTimer);
      copyTimer = setTimeout(() => (copied = null), 2000);
    } catch {
      /* clipboard unavailable (permissions) — the text stays selectable */
    }
  }
</script>

<svelte:head>
  <title>{version?.canonical_form ?? t('ver.fallback_title')} {t('typo.dash')} Kollepedia NG</title>
  {#if version}
    <meta name="description" content={stripMarkdown(version.definition_md).slice(0, 160)} />
  {/if}
</svelte:head>

<div class="container">
  {#if error}
    <p class="err ui" role="alert">{t('ver.load_error', { error })}</p>
  {:else if notFound || data.reason === 'error'}
    <EmptyState
      icon="clock"
      heading={data.reason === 'error' ? t('soft404.load_error_h') : t('soft404.version_h')}
      body={data.reason === 'error' ? t('soft404.load_error_body') : t('soft404.version_body')}
      level={1}
    >
      {#snippet actions()}
        <a class="btn btn-primary" href="/">{t('soft404.search_concepts')}</a>
        <a class="btn" href="/collections">{t('soft404.to_collections')}</a>
      {/snippet}
    </EmptyState>
  {:else if !version}
    <p class="muted ui">{t('ver.loading')}</p>
  {:else}
    <nav class="ui breadcrumb"><a href="/concepts/{version.concept_id}">{t('ver.to_concept')}</a></nav>

    <p class="frozen ui" role="note">
      <span class="frozen-icon" aria-hidden="true"><Icon name="frozen" size={15} /></span>
      {t('ver.frozen_banner')}
      {version.is_head ? t('ver.is_head_note') : t('ver.not_head_note')}
    </p>

    <article>
      <header class="head">
        <h1>{version.canonical_form}</h1>
        <div class="meta ui">
          <span class="pill pill-status-{version.status}">{statusLabel(version.status)}</span>
          <span class="pill">{languageLabel(version.language)}</span>
          {#each version.tags as tag (tag)}
            <span class="pill">{tag}</span>
          {/each}
        </div>
        <p class="byline mono">
          {#if version.created_by}
            <a class="author" href="/authors/{version.created_by.handle}"
              >{version.created_by.display_name}</a
            >
          {:else}
            {t('tm.unknown_author')}
          {/if}
          · <CollectionBadge collection={version.collection} /> · {formatDate(version.created_at)} · {t('ver.meta_version', {
            id: shortId(version.id)
          })}
        </p>
      </header>

      <!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown escapes HTML -->
      <div class="def">{@html renderMarkdown(version.definition_md)}</div>

      {#if version.note}
        <blockquote class="note">”{version.note}”</blockquote>
      {/if}

      <section class="cite card">
        <h2>{t('ver.cite_title')}</h2>
        <div class="cite-row ui">
          <p class="cite-label">{t('ver.cite_url_label')}</p>
          <div class="cite-value">
            <code class="mono">{permUrl}</code>
            <button
              type="button"
              class="btn"
              aria-label={t('ver.copy_url_aria')}
              onclick={() => copy(permUrl, 'url')}
            >
              {copied === 'url' ? t('common.copied') : t('common.copy')}
            </button>
          </div>
        </div>
        <div class="cite-row ui">
          <p class="cite-label">{t('ver.cite_line_label')}</p>
          <div class="cite-value">
            <p class="cite-line">{citation}</p>
            <button
              type="button"
              class="btn"
              aria-label={t('ver.copy_cite_aria')}
              onclick={() => copy(citation, 'cite')}
            >
              {copied === 'cite' ? t('common.copied') : t('common.copy')}
            </button>
          </div>
        </div>
      </section>

      <nav class="links ui">
        <a href="/concepts/{version.concept_id}">{t('ver.to_concept')}</a>
        <a href="/concepts/{version.concept_id}/history">{t('cmp.open_tm')}</a>
      </nav>
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

  .frozen {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    max-width: 65ch;
    margin: 0 0 var(--space-6);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent-soft);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .frozen-icon {
    display: inline-flex;
    flex-shrink: 0;
    color: var(--accent);
  }

  .head h1 {
    margin-bottom: var(--space-3);
  }

  .meta {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }

  .byline {
    color: var(--ink-3);
  }

  .author {
    color: inherit;
  }

  .author:hover {
    color: var(--accent);
  }

  .def {
    font-size: var(--text-body-lg);
    line-height: 1.75;
    max-width: 65ch;
    margin: var(--space-6) 0;
  }

  .note {
    max-width: 65ch;
    margin: var(--space-4) 0;
    padding-left: var(--space-3);
    border-left: 3px solid var(--line);
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }

  .cite {
    max-width: 65ch;
    margin: var(--space-8) 0 var(--space-6);
  }


  .cite-row {
    margin-bottom: var(--space-4);
  }

  .cite-row:last-child {
    margin-bottom: 0;
  }

  .cite-label {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin: 0 0 var(--space-1);
  }

  .cite-value {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .cite-value code {
    flex: 1;
    min-width: 200px;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-sunken);
    overflow-wrap: anywhere;
  }

  .cite-line {
    flex: 1;
    min-width: 200px;
    margin: 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-sunken);
    font-family: var(--font-serif);
    font-size: var(--text-sm);
    overflow-wrap: anywhere;
  }

  .links {
    display: flex;
    gap: var(--space-6);
    flex-wrap: wrap;
    font-size: var(--text-sm);
    margin: var(--space-6) 0;
  }
</style>
