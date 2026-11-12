<script lang="ts">
  /** /about: om Kollepedia — vision, bakgrund, licenser, kontakt. Fully bilingual —
   * the page-scale prose lives in ./content.ts (content-by-language module)
   * and is selected reactively by the current UI language. */
  import CollectionBadge from '$lib/components/CollectionBadge.svelte';
  import { onMount } from 'svelte';
  import { api, type CollectionOut } from '$lib/api';
  import { i18n, t } from '$lib/i18n.svelte';
  import { aboutContent } from './content';

  const c = $derived(aboutContent[i18n.lang]);

  let collections = $state<CollectionOut[]>([]);
  let loadFailed = $state(false);

  onMount(async () => {
    try {
      collections = await api.collections();
    } catch {
      loadFailed = true;
    }
  });

  function licenceLabel(collection: CollectionOut): string | null {
    return (collection.licence?.label as string | undefined) ?? null;
  }

  function licenceUrl(collection: CollectionOut): string | null {
    return (collection.licence?.url as string | undefined) ?? null;
  }
</script>

<svelte:head><title>{t('about.head_title')}</title></svelte:head>

<div class="container">
  <article class="about">
    <header>
      <p class="kicker ui">{c.kicker}</p>
      <h1>{c.title}</h1>
    </header>

    <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
    <p class="lede">{@html c.ledeHtml}</p>

    <section>
      <h2>{c.why.title}</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
      <p>{@html c.why.html}</p>
    </section>

    <section>
      <h2>{c.history.title}</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
      <p>{@html c.history.html}</p>
    </section>

    <section>
      <h2>{c.openSource.title}</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
      <p>{@html c.openSource.html}</p>
    </section>

    <section>
      <h2>{c.licences.title}</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
      <p>{@html c.licences.html}</p>
      {#if loadFailed}
        <p class="ui muted">{c.licences.loadFailed}</p>
      {:else if collections.length === 0}
        <p class="ui muted">{c.licences.loading}</p>
      {:else}
        <ul class="licences ui">
          {#each collections as collection (collection.id)}
            <li>
              <CollectionBadge {collection} />
              <span class="licence">
                {#if licenceUrl(collection)}
                  <a href={licenceUrl(collection)} target="_blank" rel="noopener noreferrer"
                    >{licenceLabel(collection) ?? licenceUrl(collection)}</a
                  >
                {:else if licenceLabel(collection)}
                  {licenceLabel(collection)}
                {:else}
                  {c.licences.notSpecified}
                {/if}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section>
      <h2>{c.start.title}</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
      <p>{@html c.start.html}</p>
    </section>
  </article>
</div>

<style>
  .about {
    max-width: 68ch;
    margin: 0 auto;
  }

  .kicker {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: var(--space-2);
  }

  h1 {
    margin-bottom: var(--space-6);
  }

  .lede {
    font-size: var(--text-body-lg);
    line-height: 1.7;
    color: var(--ink);
    margin-bottom: var(--space-8);
  }

  section {
    margin-bottom: var(--space-8);
  }

  h2 {
    font-size: var(--text-xl);
    margin-bottom: var(--space-3);
  }

  section p {
    line-height: 1.7;
    color: var(--ink-2);
  }

  /* Injected by {@html} from ./content.ts — needs :global to reach it. */
  .about :global(.small) {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .muted {
    color: var(--ink-3);
  }

  .licences {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
  }

  .licences li {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--line);
    font-size: var(--text-sm);
  }

  .licence {
    margin-left: auto;
    color: var(--ink-2);
  }
</style>
