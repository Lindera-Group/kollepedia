<script lang="ts">
  /** Public read-only view of the curated global categories (beslut,
   * 2026-07-11): everyone can SEE the vocabulary; only super admins curate it
   * (/admin/taxonomies). The notice explains that the system evolves and that
   * changes trigger semantic re-analysis of all concepts. */
  import { onMount } from 'svelte';
  import { api, type TaxonomyOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { i18n, t } from '$lib/i18n.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  let taxonomies = $state<TaxonomyOut[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const globalTaxonomies = $derived(taxonomies.filter((tx) => tx.scope === 'global'));

  onMount(async () => {
    try {
      taxonomies = await api.taxonomies();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>{t('cats.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('cats.h1')} intro={t('cats.intro')} />

  <p class="notice ui" role="note">
    {t('cats.change_notice')}
  </p>

  {#if loading}
    <p class="ui muted">{t('cats.loading')}</p>
  {:else if error}
    <p class="error ui" role="alert">{t('cats.load_error', { error })}</p>
  {:else if globalTaxonomies.length === 0}
    <p class="ui muted">{t('cats.none')}</p>
  {:else}
    {#each globalTaxonomies as taxonomy (taxonomy.id)}
      <section class="taxonomy">
        {#if globalTaxonomies.length > 1}
          <h2>{taxonomy.name}</h2>
        {/if}
        {#if taxonomy.description}
          <p class="ui muted description">{taxonomy.description}</p>
        {/if}
        <ul class="values">
          {#each taxonomy.values as value (value.id)}
            <li>
              <span class="pill">
                {i18n.lang === 'en' && value.name_en ? value.name_en : value.name}
              </span>
            </li>
          {/each}
        </ul>
      </section>
    {/each}
  {/if}
</div>

<style>
  /* Ändringsnotisen: informativt tillstånd, aldrig varningsrött. */
  .notice {
    max-width: 65ch;
    padding: var(--space-3) var(--space-4);
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin-bottom: var(--space-6);
  }

  .muted {
    color: var(--ink-3);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
  }

  .taxonomy {
    margin-bottom: var(--space-6);
  }

  .description {
    max-width: 60ch;
    font-size: var(--text-sm);
    margin-bottom: var(--space-3);
  }

  .values {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
</style>
