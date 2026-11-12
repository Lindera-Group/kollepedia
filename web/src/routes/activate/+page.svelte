<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { ApiError, getAuthor, type AuthorDetailOut } from '$lib/api';
  import AuthForms from '$lib/auth/AuthForms.svelte';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';

  const handle = $derived(page.url.searchParams.get('handle')?.trim().toLowerCase() ?? '');
  // Personal activation-link token (outreach): verifies the claim directly.
  const claimToken = $derived(page.url.searchParams.get('token')?.trim() ?? '');

  let author = $state<AuthorDetailOut | null>(null);
  let notFound = $state(false);
  let error = $state<string | null>(null);
  let loading = $state(true);

  $effect(() => {
    const current = handle;
    author = null;
    notFound = false;
    error = null;
    if (!current) {
      loading = false;
      return;
    }
    loading = true;
    getAuthor(current)
      .then((a) => (author = a))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) notFound = true;
        else error = errorMessage(e);
      })
      .finally(() => (loading = false));
  });

  const collectionNames = $derived(author?.collections.map((c) => c.name).join(', ') ?? '');

  function onDone(): void {
    // Claimed (or logged in) — land on the now-activated profile.
    goto(author ? `/authors/${author.handle}` : '/');
  }
</script>

<svelte:head><title>{t('act.head_title')}</title></svelte:head>

<div class="container narrow">
  {#if loading}
    <p class="ui loading">{t('act.loading')}</p>
  {:else if !handle}
    <div class="card act-card ui">
      <h1>{t('act.h1')}</h1>
      <p>
        {t('act.no_handle_1')} <a href="/authors">{t('act.no_handle_link')}</a> {t('act.no_handle_2')}
      </p>
    </div>
  {:else if notFound}
    <div class="card act-card ui">
      <h1>{t('act.notfound_h1')}</h1>
      <p>
        {t('act.notfound_1')} <strong class="mono">{handle}</strong>
        {t('act.notfound_2')}
        <a href="/authors">{t('act.notfound_link')}</a>.
      </p>
    </div>
  {:else if error}
    <p class="error ui" role="alert">{t('act.error', { error })}</p>
  {:else if author}
    <header class="head">
      <h1>{t('act.welcome', { name: author.display_name })}</h1>
      {#if author.affiliation}
        <p class="ui affiliation">{author.affiliation}</p>
      {/if}
    </header>

    {#if author.activated}
      <div class="card act-card ui">
        <p class="already">
          {t('act.already')}
        </p>
        <AuthForms prefillHandle={author.handle} initialMode="login" tabs={false} {onDone} />
      </div>
    {:else}
      <div class="card act-card ui">
        <AuthForms prefillHandle={author.handle} {claimToken} initialMode="register" tabs={false} {onDone}>
          {#snippet intro()}
            <p class="intro">
              {t('act.intro_1')}
              <strong>{author?.concept_count ?? 0} {t('common.concepts')}</strong>
              {#if collectionNames}{t('act.in')} {collectionNames}{/if} {t('act.intro_2')}
            </p>
            <p class="intro-sub">
              {t('act.intro_sub_1')} <strong class="mono">{author?.handle}</strong>
              {t('act.intro_sub_2')}
            </p>
            <p class="intro-sub">
              {claimToken ? t('act.token_hint') : t('act.review_hint')}
            </p>
          {/snippet}
        </AuthForms>
      </div>
      <p class="ui fineprint">
        {t('act.fineprint_1')} <a href="/authors/{author.handle}">{t('act.fineprint_link')}</a>.
      </p>
    {/if}
  {/if}
</div>

<style>

  .head h1 {
    margin-bottom: var(--space-2);
  }

  .affiliation {
    color: var(--ink-2);
    margin: 0 0 var(--space-4);
  }

  .intro {
    font-size: var(--text-base);
    margin: 0 0 var(--space-3);
    line-height: 1.55;
  }

  .intro-sub {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-4);
    line-height: 1.5;
  }

  .already {
    margin: 0 0 var(--space-4);
    color: var(--ink-2);
  }

  .act-card h1 {
    font-size: var(--text-xl);
    margin-bottom: var(--space-2);
  }

  .act-card p {
    margin: 0;
  }

  .act-card p + p {
    margin-top: var(--space-2);
  }

  .fineprint {
    margin-top: var(--space-4);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .error {
    padding: var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
  }

  .loading {
    color: var(--ink-3);
  }
</style>
