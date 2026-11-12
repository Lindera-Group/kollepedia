<script lang="ts">
  /** In-app manual (/manual). Fully bilingual: every section body lives in
   * ./content.ts (content-by-language module) and renders by UI language.
   * Editorial single page — sticky ToC on desktop, collapsible on mobile,
   * shared anchor ids per section (the ids are URLs — never translated),
   * :target highlight. Doubles as conceptual onboarding, especially the
   * Samlingar-vs-Listor section (VISION §3: "the one users must get").
   * Section bodies are trusted authored HTML injected with {@html}; because
   * injected nodes carry no scoped-style hash, their CSS is :global-scoped
   * under .manual (the article element, which is in the template). */
  import { i18n, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import { page } from '$app/state';
  import { NO_FEATURES } from '$lib/features';
  import { manual, SECTION_AUDIENCE, SECTION_IDS, type SectionId } from './content';

  const m = $derived(manual[i18n.lang]);
  const features = $derived(page.data.features ?? NO_FEATURES);

  // The manual adapts to the signed-in role: sections about features the
  // reader cannot reach are hidden from both the ToC and the page. SSR
  // renders the anonymous view; role sections appear after hydration.
  const loggedIn = $derived(currentUser.token !== null && currentUser.handle !== '');
  const visibleIds = $derived(
    SECTION_IDS.filter((id) => {
      // Dark features have no manual: the section and every passage marked
      // <!--ai-->…<!--/ai--> in other sections disappear with the flag.
      if (id === 'ai' && !features.ai) return false;
      const audience = SECTION_AUDIENCE[id];
      if (audience === 'all') return true;
      if (audience === 'user') return loggedIn;
      return currentUser.is_super_admin;
    })
  );

  function sectionHtml(id: SectionId): string {
    const html = m.sections[id].html;
    return features.ai
      ? html.replace(/<!--\/?ai-->/g, '')
      : html.replace(/<!--ai-->[\s\S]*?<!--\/ai-->/g, '');
  }
</script>

{#snippet tocList()}
  <ol>
    {#each visibleIds as id (id)}
      <li><a href="#{id}">{m.sections[id].title}</a></li>
    {/each}
  </ol>
{/snippet}

<svelte:head><title>{t('help.head_title')}</title></svelte:head>

<div class="container">
  <header class="manual-head">
    <p class="kicker ui">{m.kicker}</p>
    <h1>{m.title}</h1>
    <p class="lede">{m.lede}</p>
  </header>

  <details class="toc-mobile ui">
    <summary>{m.tocTitle}</summary>
    <nav aria-label={m.tocTitle}>
      {@render tocList()}
    </nav>
  </details>

  <div class="layout">
    <aside class="toc-desktop ui">
      <nav aria-label={m.tocTitle}>
        <p class="toc-title">{m.tocTitle}</p>
        {@render tocList()}
      </nav>
    </aside>

    <article class="manual">
      {#each visibleIds as id (id)}
        <section {id} aria-labelledby="h-{id}">
          <h2 id="h-{id}">
            {m.sections[id].title}
            <a class="anchor" href="#{id}" aria-label={t('help.anchor_to', { title: m.sections[id].title })}>#</a>
          </h2>
          <!-- eslint-disable-next-line svelte/no-at-html-tags — trusted authored manual content from ./content.ts -->
          {@html sectionHtml(id)}
        </section>
      {/each}

      <footer class="manual-foot ui">
        <p>{m.foot}</p>
      </footer>
    </article>
  </div>
</div>

<style>
  /* ── Page header ── */
  .manual-head {
    max-width: 68ch;
    padding: 0 0 var(--space-6);
  }

  .kicker {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: var(--space-2);
  }

  .manual-head h1 {
    margin-bottom: var(--space-4);
  }

  .lede {
    font-size: var(--text-lg);
    color: var(--ink-2);
    line-height: 1.6;
    margin: 0;
  }

  /* ── Layout: sticky ToC + measure-limited article ── */
  .layout {
    display: grid;
    grid-template-columns: 230px minmax(0, 1fr);
    gap: var(--space-12);
    align-items: start;
  }

  .toc-desktop {
    position: sticky;
    top: calc(var(--space-16) + var(--space-2));
    font-size: var(--text-sm);
  }

  .toc-title {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-3);
  }

  .toc-desktop ol,
  .toc-mobile ol {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: toc;
  }

  .toc-desktop li,
  .toc-mobile li {
    counter-increment: toc;
  }

  .toc-desktop a,
  .toc-mobile a {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
    padding: 0.32em 0;
    color: var(--ink-2);
    text-decoration: none;
    border-left: 2px solid transparent;
    padding-left: var(--space-2);
    margin-left: calc(-1 * var(--space-2));
    transition: color 0.15s, border-color 0.15s;
  }

  .toc-desktop a::before,
  .toc-mobile a::before {
    content: counter(toc, decimal-leading-zero);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .toc-desktop a:hover,
  .toc-mobile a:hover {
    color: var(--accent);
    border-left-color: var(--accent);
  }

  .toc-mobile {
    display: none;
    margin-bottom: var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-raised);
    font-size: var(--text-sm);
  }

  .toc-mobile summary {
    cursor: pointer;
    font-weight: 600;
    color: var(--ink-2);
  }

  .toc-mobile nav {
    padding-top: var(--space-3);
  }

  @media (max-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }

    .toc-desktop {
      display: none;
    }

    .toc-mobile {
      display: block;
    }
  }

  /* ── Article typography (editorial: serif body, ~68ch measure) ──
     Section bodies arrive via {@html}, so descendant selectors are
     :global-scoped under .manual (the article stays a template element). */
  .manual {
    max-width: 68ch;
    font-size: var(--text-body-lg);
    line-height: 1.75;
    counter-reset: chapter;
  }

  .manual section {
    counter-increment: chapter;
    margin-bottom: var(--space-12);
    scroll-margin-top: calc(var(--space-16) + var(--space-4));
  }

  .manual h2 {
    font-weight: 600;
    margin: 0 0 var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--line);
  }

  .manual h2::before {
    content: counter(chapter, decimal-leading-zero);
    display: block;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    letter-spacing: 0.12em;
    color: var(--accent);
    margin-bottom: var(--space-1);
  }

  .manual :global(h3) {
    font-size: var(--text-lg);
    font-weight: 600;
    margin: var(--space-6) 0 var(--space-3);
  }

  /* :target highlight — arriving via a ToC/anchor link marks the section */
  .manual section:target {
    border-left: 3px solid var(--accent);
    padding-left: var(--space-4);
    margin-left: calc(-1 * var(--space-4) - 3px);
  }

  .manual section:target > h2 {
    border-top-color: var(--accent);
  }

  /* Per-heading anchor links (keyboard reachable, discreet) */
  .anchor {
    font-family: var(--font-mono);
    font-size: 0.6em;
    font-weight: 400;
    color: var(--ink-3);
    text-decoration: none;
    opacity: 0;
    transition: opacity 0.15s;
    vertical-align: 0.25em;
    margin-left: 0.35em;
  }

  .manual h2:hover .anchor,
  .anchor:focus-visible {
    opacity: 1;
  }

  .anchor:hover {
    color: var(--accent);
  }

  .manual :global(ul),
  .manual :global(ol) {
    padding-left: 1.4em;
    margin: 0 0 var(--space-4);
  }

  .manual :global(li) {
    margin-bottom: var(--space-2);
  }

  .manual :global(li)::marker {
    color: var(--ink-3);
    font-family: var(--font-sans);
    font-size: 0.9em;
  }

  .manual :global(code) {
    font-family: var(--font-mono);
    font-size: 0.82em;
    background: var(--bg-sunken);
    border-radius: var(--radius-sm);
    padding: 0.1em 0.35em;
  }

  .manual :global(pre) {
    overflow-x: auto;
    background: var(--bg-sunken);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    font-size: var(--text-sm);
    margin: 0 0 var(--space-4);
  }

  .manual :global(pre code) {
    background: none;
    padding: 0;
    font-size: var(--text-xs);
  }

  .manual :global(kbd) {
    font-family: var(--font-mono);
    font-size: 0.75em;
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: var(--radius-sm);
    background: var(--bg-raised);
    padding: 0.1em 0.45em;
    white-space: nowrap;
  }

  /* ── Samling vs Lista twin cards ── */
  .manual :global(.duo) {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin: var(--space-6) 0;
  }

  @media (max-width: 640px) {
    .manual :global(.duo) {
      grid-template-columns: 1fr;
    }
  }

  .manual :global(.duo-card) {
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    padding: var(--space-4) var(--space-6);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .manual :global(.duo-card h3) {
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    margin: 0 0 var(--space-1);
  }

  .manual :global(.duo-card:first-child) {
    border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
  }

  .manual :global(.duo-tag) {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: var(--space-3);
  }

  .manual :global(.duo-card p:last-child) {
    margin-bottom: 0;
  }

  .manual :global(.rule-of-thumb) {
    border-left: 3px solid var(--accent);
    background: var(--accent-soft);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    padding: var(--space-3) var(--space-4);
  }

  /* ── Import column table ── */
  .manual :global(.table-scroll) {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    margin: 0 0 var(--space-4);
  }

  .manual :global(.table-scroll table) {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .manual :global(.table-scroll th) {
    text-align: left;
    font-weight: 600;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
  }

  .manual :global(.table-scroll td) {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: baseline;
  }

  .manual :global(.table-scroll tbody tr:last-child td) {
    border-bottom: none;
  }

  .manual-foot {
    border-top: 1px solid var(--line);
    padding-top: var(--space-4);
    font-size: var(--text-sm);
    color: var(--ink-3);
  }

  .manual-foot p {
    margin: 0;
  }
</style>
