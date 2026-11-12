<script lang="ts">
  import type { AnnotationOut } from '$lib/api';
  import { peerColor } from '$lib/collab/helpers';
  import { t } from '$lib/i18n.svelte';
  import { renderMarkdown } from '$lib/text';

  import { buildSegments, sourceCitations, type SectionAuthor } from './sections';

  let {
    definitionMd,
    annotations
  }: { definitionMd: string; annotations: AnnotationOut[] } = $props();

  const segments = $derived.by(() => {
    if (!annotations.some((a) => a.attr_type === 'section')) return null;
    const built = buildSegments(definitionMd, annotations);
    if (built === null) {
      console.warn(
        'SectionedDefinition: sektionsoffsets rekonstruerar inte definitionstexten – visar hela definitionen osektionerad.'
      );
    }
    return built;
  });

  const citations = $derived(sourceCitations(annotations));

  /** Author annotations carry user_id/handle since migration 003 — map each
   * byline author (same dedup key as sections.ts) to their /authors profile. */
  const authorHandles = $derived.by(() => {
    const map = new Map<string, string>();
    for (const a of annotations) {
      if (a.attr_type !== 'author') continue;
      const value = a.value as { name?: unknown; web_url?: unknown; handle?: unknown };
      const name = typeof value.name === 'string' ? value.name.trim() : '';
      const handle = typeof value.handle === 'string' ? value.handle.trim() : '';
      if (!name || !handle) continue;
      const webUrl = typeof value.web_url === 'string' && value.web_url.trim() !== '' ? value.web_url.trim() : '';
      map.set(`${name}|${webUrl}`, handle);
    }
    return map;
  });

  function authorKey(author: SectionAuthor): string {
    return `${author.name}|${author.web_url ?? ''}`;
  }

  function profileHandle(author: SectionAuthor): string | null {
    return authorHandles.get(authorKey(author)) ?? null;
  }

  /** Attributionslagret (paket C, beslut 2): a stable, discreet colour per
   * author — peerColor of the handle (falling back to the name). */
  function authorColor(author: SectionAuthor): string {
    return peerColor(profileHandle(author) ?? author.name);
  }

  // Bidirectional hover (paket C): author name ↔ the sections they wrote.
  let hoveredAuthor = $state<string | null>(null);
  let hoveredSection = $state<number | null>(null);

  function sectionMatches(authors: SectionAuthor[]): boolean {
    return hoveredAuthor !== null && authors.some((a) => authorKey(a) === hoveredAuthor);
  }

  function hoveredColor(authors: SectionAuthor[]): string | null {
    if (hoveredAuthor === null) return null;
    const author = authors.find((a) => authorKey(a) === hoveredAuthor);
    return author ? authorColor(author) : null;
  }
</script>

<div class="definition">
  {#if segments}
    {#each segments as segment, i (i)}
      <!-- Hovern är rent dekorativ (bylinen är alltid synlig) — gruppen
           namnges av sektionsnumret/titeln när de finns. -->
      <section
        class="def-section"
        class:hl={sectionMatches(segment.authors)}
        style:--author-color={hoveredColor(segment.authors)}
        role="group"
        onmouseenter={() => (hoveredSection = i)}
        onmouseleave={() => (hoveredSection = null)}
      >
        {#if segment.number || segment.title}
          <h3 class="section-head">
            {#if segment.number}<span class="section-num">§ {segment.number}</span>{/if}
            {#if segment.title}<span class="section-title">{segment.title}</span>{/if}
          </h3>
        {/if}
        <!-- eslint-disable-next-line svelte/no-at-html-tags — renderMarkdown escapes first -->
        {@html renderMarkdown(segment.text)}
        {#if segment.authors.length}
          <!-- Beslut 5 (2026-07-12): names only under the definition — no
               affiliation, no tooltips. Everything else lives one click away
               on the author page. Hovering a name washes the author's
               sections in their colour; hovering a section lifts its byline. -->
          <p class="byline ui" class:emph={hoveredSection === i}>
            <span aria-hidden="true">{t('typo.dash')}</span>
            {#each segment.authors as author, j (authorKey(author))}
              {#if j > 0}<span class="byline-sep" aria-hidden="true">·</span>{/if}
              <span class="byline-author" style:--author-color={authorColor(author)}>
                {#if profileHandle(author)}
                  <a
                    class="byline-link"
                    href="/authors/{profileHandle(author)}"
                    onmouseenter={() => (hoveredAuthor = authorKey(author))}
                    onmouseleave={() => (hoveredAuthor = null)}
                    onfocus={() => (hoveredAuthor = authorKey(author))}
                    onblur={() => (hoveredAuthor = null)}>{author.name}</a
                  >
                {:else if author.web_url}
                  <a
                    class="byline-link"
                    href={author.web_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={t('sections.external_profile_aria', { name: author.name })}
                    onmouseenter={() => (hoveredAuthor = authorKey(author))}
                    onmouseleave={() => (hoveredAuthor = null)}
                    onfocus={() => (hoveredAuthor = authorKey(author))}
                    onblur={() => (hoveredAuthor = null)}
                    >{author.name}<span class="ext" aria-hidden="true">↗</span></a
                  >
                {:else}
                  <span class="byline-plain">{author.name}</span>
                {/if}
              </span>
            {/each}
          </p>
        {/if}
      </section>
    {/each}
  {:else}
    <!-- eslint-disable-next-line svelte/no-at-html-tags — renderMarkdown escapes first -->
    {@html renderMarkdown(definitionMd)}
  {/if}

  {#if citations.length}
    <div class="sources ui">
      {#each citations as citation (citation)}
        <p class="source">{t('sections.source_prefix')} {citation}</p>
      {/each}
    </div>
  {/if}
</div>

<style>
  .definition {
    font-size: var(--text-body-lg);
    line-height: 1.75;
    max-width: 65ch;
    margin: var(--space-6) 0;
  }

  /* The transparent border + compensated margin keep the text column still
     when a hover adds the author-coloured edge — zero layout shift. */
  .def-section {
    margin: 0 0 var(--space-6) calc(-1 * (var(--space-3) + 2px));
    padding-left: var(--space-3);
    border-left: 2px solid transparent;
    border-radius: var(--radius-sm);
    transition:
      background-color 0.15s,
      border-color 0.15s;
  }

  .def-section:last-of-type {
    margin-bottom: 0;
  }

  .def-section.hl {
    background: color-mix(in srgb, var(--author-color, var(--accent)) 9%, transparent);
    border-left-color: var(--author-color, var(--accent));
  }

  .section-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    margin: 0 0 var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 400;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .section-num {
    color: var(--ink-3); /* WCAG AA: sepia failed 4.5:1 against the paper bg */
    white-space: nowrap;
  }

  .section-title {
    color: var(--ink-2);
  }

  .byline {
    margin: calc(-1 * var(--space-2)) 0 0;
    font-size: var(--text-sm);
    color: var(--ink-3);
    transition: color 0.15s;
  }

  .byline.emph {
    color: var(--ink-2);
  }

  .byline-sep {
    margin: 0 var(--space-1);
  }

  .byline-author {
    white-space: normal;
  }

  /* Beslut 2: per-author colour as the DEFAULT, executed discreetly — a thin
     coloured underline under each name, intensified on hover/focus. */
  .byline-link {
    color: inherit;
    text-decoration: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 0.2em;
    text-decoration-color: color-mix(in srgb, var(--author-color, var(--ink-3)) 55%, transparent);
  }

  .byline-link:hover,
  .byline-link:focus-visible {
    color: var(--ink);
    text-decoration-color: var(--author-color, var(--accent));
  }

  .byline-plain {
    color: inherit;
  }

  .ext {
    font-size: 0.8em;
    margin-left: 0.15em;
  }

  .sources {
    margin-top: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--line);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .source {
    margin: 0 0 var(--space-1);
  }
</style>
