<script lang="ts">
  /** /pricing: tiers, comparison table and principles. Fully bilingual — the
   * page-scale prose lives in ./content.ts (content-by-language module) and is
   * selected reactively by the current UI language. */
  import { i18n, t } from '$lib/i18n.svelte';
  import { NO_MARKS, pricingContent, type Tier } from './content';

  const c = $derived(pricingContent[i18n.lang]);
</script>

<svelte:head>
  <title>{t('pricing.head_title')}</title>
  <meta name="description" content={c.metaDescription} />
</svelte:head>

<div class="container">
  <header class="hero">
    <h1>{c.heroTitle}</h1>
    <p class="tagline">{c.heroTagline}</p>
  </header>

  {#snippet tierCard(tier: Tier)}
    <article class="tier card" class:highlight={tier.highlight}>
      <h2>{tier.name}</h2>
      <p class="price">{tier.price}</p>
      <p class="audience ui">{tier.audience}</p>
      <ul class="ui">
        {#each tier.features as feature (feature)}
          <li>{feature}</li>
        {/each}
      </ul>
      {#if tier.note}
        <p class="note ui">{tier.note}</p>
      {/if}
      {#if tier.cta}
        {@const external = tier.cta.href.startsWith('http')}
        <a
          class="btn cta"
          class:btn-primary={tier.highlight}
          href={tier.cta.href}
          target={external ? '_blank' : undefined}
          rel={external ? 'noopener noreferrer' : undefined}>{tier.cta.label}</a
        >
      {/if}
    </article>
  {/snippet}

  <h2 class="group-title mono">{c.groupIndividuals}</h2>
  <div class="tiers individuals">
    {#each c.tiers.slice(0, 2) as tier (tier.name)}
      {@render tierCard(tier)}
    {/each}
  </div>

  <h2 class="group-title mono">{c.groupOrgs}</h2>
  <div class="tiers orgs">
    {#each c.tiers.slice(2) as tier (tier.name)}
      {@render tierCard(tier)}
    {/each}
  </div>

  <section class="compare">
    <h2>{c.compareTitle}</h2>
    <div class="scroll">
      <table class="ui">
        <thead>
          <tr>
            <th scope="col">{c.featureColumn}</th>
            {#each c.tierColumns as column (column)}
              <th scope="col">{column}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each c.table as row (row.label)}
            <tr>
              <th scope="row">{row.label}</th>
              {#each row.values as value, i (i)}
                <td class:no={NO_MARKS.has(value)}>{value}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>

  <section class="principles">
    <h2>{c.principlesTitle}</h2>
    <ul>
      {#each c.principles as principle (principle.strong)}
        <li><strong>{principle.strong}</strong> {principle.text}</li>
      {/each}
    </ul>
    <!-- eslint-disable-next-line svelte/no-at-html-tags — static authored content from ./content.ts -->
    <p class="ui contact">{@html c.contactHtml}</p>
  </section>
</div>

<style>
  .hero {
    padding: 0 0 var(--space-6);
    max-width: 62ch;
  }


  .tagline {
    color: var(--ink-2);
    font-size: var(--text-lg);
  }

  .group-title {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--ink-3);
    font-weight: 400;
    margin: var(--space-8) 0 var(--space-3);
  }

  .tiers {
    display: grid;
    gap: var(--space-4);
    align-items: start;
  }

  .tiers.individuals {
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  }

  .tiers.orgs {
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    margin-bottom: var(--space-12);
  }

  .tier h2 {
    font-size: var(--text-lg);
    margin-bottom: var(--space-1);
  }

  .tier.highlight {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
  }

  .price {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--space-2);
  }

  .audience {
    color: var(--ink-3);
    font-size: var(--text-sm);
    min-height: 3em;
  }

  .tier ul {
    padding-left: 1.1em;
    margin: var(--space-3) 0;
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .tier .note {
    font-size: var(--text-xs);
    color: var(--ink-3);
    font-style: italic;
  }

  .cta {
    display: inline-block;
    margin-top: var(--space-2);
    text-decoration: none;
  }

  .compare h2,
  .principles h2 {
    margin-bottom: var(--space-4);
  }

  .scroll {
    overflow-x: auto;
    margin-bottom: var(--space-12);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    min-width: 720px;
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line);
  }

  thead th {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-3);
  }

  tbody th {
    font-weight: 500;
    color: var(--ink-2);
  }

  td {
    text-align: center;
    color: var(--accent);
    font-weight: 600;
  }

  td.no {
    color: var(--ink-3);
    font-weight: 400;
  }

  .principles ul {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    max-width: 68ch;
  }

  .contact {
    margin-top: var(--space-8);
    color: var(--ink-2);
  }
</style>
