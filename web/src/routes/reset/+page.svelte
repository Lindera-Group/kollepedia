<script lang="ts">
  /** Password reset (iteration 3): consumes a one-time admin-created token from
   * /reset?token=… — no email infra, links are handed over manually. */
  import { page } from '$app/state';
  import Icon from '$lib/icons/Icon.svelte';
  import { night4, resetPassword } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { PASSWORD_MIN_LENGTH, validateNewPassword } from '$lib/auth/password';
  import { t } from '$lib/i18n.svelte';

  const token = $derived(page.url.searchParams.get('token') ?? '');

  let password = $state('');
  let confirmation = $state('');
  let busy = $state(false);
  let error = $state<string | null>(null);
  let done = $state(false);

  // ── Forgot password (iteration 4): no token → self-service email flow.
  // The response is ALWAYS neutral — no account enumeration. ──
  let forgotId = $state('');
  let forgotBusy = $state(false);
  let forgotDone = $state(false);
  let forgotError = $state<string | null>(null);

  async function submitForgot(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!forgotId.trim()) return;
    forgotBusy = true;
    forgotError = null;
    try {
      await night4.forgot(forgotId.trim());
      forgotDone = true;
    } catch (e) {
      forgotError = t('profile.forgot_error', {
        error: errorMessage(e)
      });
    } finally {
      forgotBusy = false;
    }
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = validateNewPassword(password, confirmation);
    if (error) return;
    busy = true;
    try {
      await resetPassword(token, password);
      done = true;
    } catch (e) {
      error = errorMessage(e);
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>{t('rst.head_title')}</title></svelte:head>

<div class="container">
  <div class="reset card ui">
    <h1>{t('rst.h1')}</h1>

    {#if !token}
      <p class="explain">
        {t('rst.no_token')}
      </p>

      <section class="forgot" aria-labelledby="forgot-h2">
        <h2 id="forgot-h2">{t('profile.forgot_h2')}</h2>
        {#if forgotDone}
          <p class="success" role="status"><Icon name="check" size={14} /> {t('profile.forgot_done')}</p>
        {:else}
          <p class="explain">{t('profile.forgot_body')}</p>
          <form onsubmit={submitForgot} aria-label={t('profile.forgot_h2')}>
            <div class="field">
              <label for="forgot-id">{t('profile.forgot_label')}</label>
              <input
                id="forgot-id"
                class="input"
                type="text"
                bind:value={forgotId}
                autocomplete="username"
                spellcheck="false"
                disabled={forgotBusy}
              />
            </div>
            {#if forgotError}
              <p class="error" role="alert">{forgotError}</p>
            {/if}
            <button type="submit" class="btn btn-primary" disabled={forgotBusy || !forgotId.trim()}>
              {forgotBusy ? t('profile.forgot_sending') : t('profile.forgot_send')}
            </button>
          </form>
        {/if}
      </section>

      <p><a href="/">{t('common.to_home')}</a></p>
    {:else if done}
      <p class="success" role="status"><Icon name="check" size={14} /> {t('rst.done')}</p>
      <p class="explain">
        {t('rst.done_1')} <strong>{t('auth.login')}</strong> {t('rst.done_2')}
      </p>
      <p><a href="/">{t('common.to_home')}</a></p>
    {:else}
      <p class="explain">
        {t('rst.explain')}
      </p>
      <form onsubmit={submit} aria-label={t('rst.form_aria')}>
        <div class="field">
          <label for="reset-password">{t('rst.new_password')}</label>
          <input
            id="reset-password"
            class="input"
            type="password"
            bind:value={password}
            autocomplete="new-password"
            minlength={PASSWORD_MIN_LENGTH}
            required
            disabled={busy}
          />
        </div>
        <div class="field">
          <label for="reset-confirm">{t('rst.repeat')}</label>
          <input
            id="reset-confirm"
            class="input"
            type="password"
            bind:value={confirmation}
            autocomplete="new-password"
            minlength={PASSWORD_MIN_LENGTH}
            required
            disabled={busy}
          />
        </div>
        {#if error}
          <p class="error" role="alert">{error}</p>
        {/if}
        <button type="submit" class="btn btn-primary" disabled={busy}>
          {busy ? t('common.saving') : t('rst.change')}
        </button>
      </form>
    {/if}
  </div>
</div>

<style>
  .reset {
    max-width: 440px;
    margin: var(--space-8) auto;
  }

  h1 {
    font-size: var(--text-xl);
    margin-bottom: var(--space-3);
  }

  .forgot {
    margin: var(--space-6) 0 var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--line);
  }

  .forgot h2 {
    font-size: var(--text-base);
    font-weight: 600;
    margin-bottom: var(--space-2);
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

  .field {
    margin-bottom: var(--space-3);
  }

  label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  input {
    width: 100%;
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-3);
  }
</style>
