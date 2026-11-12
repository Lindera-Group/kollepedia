<script lang="ts">
  /** Verify email (iteration 4): consumes the one-time ?token= from the
   * verification email (found in the admin outbox during testing). */
  import { page } from '$app/state';
  import Icon from '$lib/icons/Icon.svelte';
  import { night4 } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';

  const token = $derived(page.url.searchParams.get('token') ?? '');

  type Status = 'no-token' | 'verifying' | 'done' | 'failed';
  let status = $state<Status>('verifying');
  let error = $state('');

  $effect(() => {
    const current = token;
    if (!current) {
      status = 'no-token';
      return;
    }
    status = 'verifying';
    night4
      .verifyEmail(current)
      .then(() => (status = 'done'))
      .catch((e) => {
        error = errorMessage(e);
        status = 'failed';
      });
  });
</script>

<svelte:head><title>{t('profile.verify_head_title')}</title></svelte:head>

<div class="container">
  <div class="verify card ui">
    <h1>{t('profile.verify_h1')}</h1>

    {#if status === 'no-token'}
      <p class="explain">{t('profile.verify_no_token')}</p>
      <p><a href="/">{t('common.to_home')}</a></p>
    {:else if status === 'verifying'}
      <p class="explain" role="status" aria-live="polite">{t('profile.verify_wait')}</p>
    {:else if status === 'done'}
      <p class="success" role="status"><Icon name="check" size={14} /> {t('profile.verify_done')}</p>
      <p class="explain">{t('profile.verify_done_body')}</p>
      <p><a href="/profile">{t('profile.verify_to_profile')}</a></p>
    {:else}
      <p class="error" role="alert">{t('profile.verify_failed', { error })}</p>
      <p><a href="/">{t('common.to_home')}</a></p>
    {/if}
  </div>
</div>

<style>
  .verify {
    max-width: 440px;
    margin: var(--space-8) auto;
  }

  h1 {
    font-size: var(--text-xl);
    margin-bottom: var(--space-3);
  }

  .explain {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-4);
  }

  .success {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-base);
    color: var(--ins-strong);
    margin: 0 0 var(--space-2);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    background: var(--del-wash);
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
    margin: 0 0 var(--space-3);
  }
</style>
