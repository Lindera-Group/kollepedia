<script lang="ts">
  /** /collections/share: vägen från privat samling till delad — skapa eller
   * gå med i en organisation (gratis individlicens → organisationslicens).
   * Statiskt barn till samlingsnavet; prosan bor i ./content.ts och väljs
   * reaktivt per UI-språk (pricing-mönstret). */
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { i18n, t } from '$lib/i18n.svelte';
  import { shareContent } from './content';

  const c = $derived(shareContent[i18n.lang]);
</script>

<svelte:head>
  <title>{t('coll.share_head_title')}</title>
  <meta name="description" content={c.metaDescription} />
</svelte:head>

<div class="container narrow">
  <nav class="ui breadcrumb"><a href="/collections">{t('coll.breadcrumb_all')}</a></nav>

  <PageHeader title={c.title} intro={c.intro} />

  <section>
    <h2>{c.whyTitle}</h2>
    <p>{c.whyText}</p>
  </section>

  <section>
    <h2>{c.pathsTitle}</h2>
    <div class="paths">
      {#each c.steps as step (step.title)}
        <article class="path card">
          <h3>{step.title}</h3>
          <p>{step.text}</p>
          {#if step.cta}
            <p class="cta-row"><a class="btn ui" href={step.cta.href}>{step.cta.label}</a></p>
          {/if}
        </article>
      {/each}
    </div>
  </section>

  <section>
    <h2>{c.moveTitle}</h2>
    <p>{c.moveText}</p>
  </section>
</div>

<style>
  section {
    margin-bottom: var(--space-8);
  }

  h2 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-2);
  }

  p {
    margin: 0;
    line-height: 1.6;
  }

  .paths {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .path {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .path h3 {
    font-size: var(--text-base);
    margin: 0;
  }

  .path p {
    flex: 1;
    font-size: var(--text-sm);
    line-height: 1.55;
    color: var(--ink-2);
  }

  .cta-row {
    flex: 0 0 auto;
  }
</style>
