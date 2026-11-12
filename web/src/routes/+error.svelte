<script lang="ts">
  /** Root error boundary — the LAST safety net (paket D). The resource
   * routes render soft in-page states instead of throwing, so this page is
   * only reached for unknown routes and unexpected failures. It never
   * renders the raw error message — localized copy only. */
  import { page } from '$app/state';
  import { t } from '$lib/i18n.svelte';

  const notFound = $derived(page.status === 404);
</script>

<svelte:head>
  <title>{page.status} {t('typo.dash')} Kollepedia NG</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="container">
  <div class="card errbox ui">
    <p class="code mono">{page.status}</p>
    <h1>{notFound ? t('errpage.notfound_h1') : t('errpage.generic_h1')}</h1>
    <p class="body">
      {#if notFound}
        {t('errpage.notfound_body')}
      {:else}
        {t('errpage.generic_body')}
      {/if}
    </p>
    <p><a href="/">← {t('errpage.home_link')}</a></p>
  </div>
</div>

<style>
  .errbox {
    max-width: 55ch;
    margin: var(--space-8) auto;
    padding: var(--space-8);
    text-align: center;
  }

  .code {
    font-size: var(--text-xl);
    color: var(--ink-3);
    margin: 0 0 var(--space-2);
  }

  .errbox h1 {
    margin-bottom: var(--space-3);
  }

  .body {
    color: var(--ink-2);
    margin-bottom: var(--space-4);
  }

  .errbox a {
    color: var(--accent);
  }
</style>
