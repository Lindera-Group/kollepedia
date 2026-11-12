<script lang="ts">
  /** Login/registration tabs — account-only (the anonymous signature path was
   * removed in the SPAM-hardening pass; every write must be attributable).
   * - Login: email OR username + password.
   * - Register: username, display name (author name), email, password — in
   *   that order — plus an invisible self-hosted bot check (proof of work,
   *   solved in the background while the form is filled in; no third-party
   *   CAPTCHA) and a honeypot field.
   * - Claim flow (/activate?handle=…): the claimed username is read-only and
   *   sent with claim=true so the imported author identity is taken over.
   * - Collisions with imported, unclaimed identities (username or email) get
   *   a pointer to the author page + the claim flow instead of a dead end.
   * - Flagged registrations show the manual-review notice. */
  import type { Snippet } from 'svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError, type AuthOut, type PowSolution } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { PASSWORD_MIN_LENGTH } from '$lib/auth/password';
  import { fetchAndSolve } from '$lib/auth/pow';
  import { t } from '$lib/i18n.svelte';
  import { setSession, type Session } from '$lib/user.svelte';

  let {
    onDone,
    prefillHandle = '',
    claimToken = '',
    initialMode = 'login',
    tabs = true,
    intro
  }: {
    onDone: () => void;
    prefillHandle?: string;
    /** Personal activation-link token (/activate?token=…) — sent with the
     * claim so it is verified directly instead of manually reviewed. */
    claimToken?: string;
    initialMode?: 'login' | 'register';
    /** false locks the form to initialMode and hides the tab bar — the
     * claim flow (/activate) is register-only, so a login tab misleads. */
    tabs?: boolean;
    intro?: Snippet;
  } = $props();

  // svelte-ignore state_referenced_locally — props seed the initial form state on purpose
  let mode = $state<'login' | 'register'>(initialMode);
  let identifier = $state('');
  // svelte-ignore state_referenced_locally
  let username = $state(prefillHandle);
  let displayName = $state('');
  let email = $state('');
  let password = $state('');
  let website = $state(''); // honeypot — humans never see or fill this
  let error = $state<string | null>(null);
  let busy = $state(false);
  // Structured collision pointer ({code, handle}) → claim links.
  let pointer = $state<{ code: string; handle: string } | null>(null);
  // Post-registration confirmation before closing.
  let registeredEmail = $state<string | null>(null);
  let pendingReview = $state(false);

  // Bot check: solve in the background as soon as the register tab is active,
  // so submission is instant for humans.
  let pow = $state<PowSolution | null>(null);
  let powState = $state<'idle' | 'running' | 'done' | 'failed'>('idle');

  $effect(() => {
    if (mode === 'register' && powState === 'idle') {
      powState = 'running';
      fetchAndSolve()
        .then((solution) => {
          pow = solution;
          powState = 'done';
        })
        .catch(() => {
          powState = 'failed';
        });
    }
  });

  function applySession(result: AuthOut): void {
    const session: Session = {
      handle: result.user.handle,
      display_name: result.user.display_name,
      token: result.token,
      is_super_admin: result.user.is_super_admin,
      review_status: result.user.review_status ?? 'approved',
      memberships: (result.user.memberships ?? []).map((m) => ({
        ...m,
        role: m.role as 'admin' | 'editor' | 'viewer'
      }))
    };
    setSession(session);
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    pointer = null;
    if (mode === 'login') {
      if (!identifier.trim() || !password) {
        error = t('profile.auth_error_login_missing');
        return;
      }
    } else {
      if (!username.trim() || !email.trim() || !password) {
        error = t('profile.auth_error_register_missing');
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
        error = t('profile.email_invalid');
        return;
      }
      if (password.length < PASSWORD_MIN_LENGTH) {
        error = t('password.too_short');
        return;
      }
      if (powState === 'failed') {
        error = t('auth.pow_failed');
        return;
      }
    }
    busy = true;
    try {
      if (mode === 'login') {
        const result = await api.login({ identifier: identifier.trim(), password });
        applySession(result);
        onDone();
      } else {
        // Wait for the background bot check if it has not finished yet.
        const solution = pow ?? (await fetchAndSolve());
        const result = await api.register({
          email: email.trim(),
          display_name: displayName.trim() || username.trim(),
          password,
          handle: username.trim(),
          ...(prefillHandle ? { claim: true } : {}),
          ...(prefillHandle && claimToken ? { claim_token: claimToken } : {}),
          pow: solution,
          website
        });
        // The solution is single-use — a retry needs a fresh one.
        pow = null;
        powState = 'idle';
        applySession(result);
        registeredEmail = email.trim();
        pendingReview = result.user.review_status === 'pending';
      }
    } catch (e) {
      pow = null;
      powState = mode === 'register' ? 'idle' : powState;
      error = errorMessage(e);
      if (e instanceof ApiError && e.code) {
        // Collision pointer ({code, params: {handle}}) → claim links.
        const handle = e.params?.handle;
        if (typeof handle === 'string' && handle) {
          pointer = { code: e.code, handle };
        }
      }
    } finally {
      busy = false;
    }
  }

  function onForgot(event: MouseEvent): void {
    event.preventDefault();
    onDone();
    void goto('/reset');
  }
</script>

<div class="authforms ui">
  {#if intro}
    {@render intro()}
  {/if}

  {#if registeredEmail}
    <div class="registered" role="status">
      {#if pendingReview}
        <p class="registered-h pending"><Icon name="clock" size={14} /> {t('profile.auth_review_pending_h')}</p>
        <p class="registered-body">
          {t('profile.auth_review_pending_body')}
        </p>
      {:else}
        <p class="registered-h"><Icon name="check" size={14} /> {t('profile.auth_registered_h')}</p>
        <p class="registered-body">
          {t('profile.auth_registered_body', { email: registeredEmail })}
        </p>
      {/if}
      <button type="button" class="btn btn-primary" onclick={onDone}>
        {t('profile.auth_registered_done')}
      </button>
    </div>
  {:else}
    {#if tabs}
      <div class="tabs" role="tablist" aria-label={t('auth.tabs_aria')}>
        <button
          type="button"
          role="tab"
          class="tab"
          aria-selected={mode === 'login'}
          onclick={() => {
            mode = 'login';
            error = null;
            pointer = null;
          }}
        >
          {t('auth.login')}
        </button>
        <button
          type="button"
          role="tab"
          class="tab"
          aria-selected={mode === 'register'}
          onclick={() => {
            mode = 'register';
            error = null;
            pointer = null;
          }}
        >
          {t('auth.register')}
        </button>
      </div>
    {/if}

    <form onsubmit={submit}>
      {#if mode === 'login'}
        <div class="field">
          <label for="auth-identifier">{t('profile.auth_identifier_label')}</label>
          <input
            id="auth-identifier"
            class="input"
            type="text"
            bind:value={identifier}
            placeholder={t('profile.auth_email_placeholder')}
            autocomplete="username"
            spellcheck="false"
          />
        </div>
      {:else}
        {#if prefillHandle}
          <p class="claim">
            <span class="claim-label">{t('profile.auth_claim_handle_label')}</span>
            <strong class="mono">{prefillHandle}</strong>
          </p>
        {:else}
          <div class="field">
            <label for="auth-username">{t('auth.username_label')}</label>
            <input
              id="auth-username"
              class="input"
              type="text"
              bind:value={username}
              placeholder={t('auth.username_placeholder')}
              autocomplete="username"
              spellcheck="false"
            />
            <p class="hint">{t('auth.username_hint')}</p>
          </div>
        {/if}
        <div class="field">
          <label for="auth-display-name">{t('auth.display_name_label')}</label>
          <input
            id="auth-display-name"
            class="input"
            type="text"
            bind:value={displayName}
            placeholder={t('auth.display_name_placeholder')}
            autocomplete="name"
          />
        </div>
        <div class="field">
          <label for="auth-email">{t('profile.auth_email_label')}</label>
          <input
            id="auth-email"
            class="input"
            type="email"
            bind:value={email}
            placeholder={t('profile.auth_email_placeholder')}
            autocomplete="email"
            spellcheck="false"
          />
        </div>
        <!-- Honeypot: visually removed; bots that fill it are rejected. -->
        <div class="hp" aria-hidden="true">
          <label for="auth-website">Website</label>
          <input id="auth-website" class="input" type="text" bind:value={website} tabindex="-1" autocomplete="off" />
        </div>
      {/if}
      <div class="field">
        <label for="auth-password">{t('auth.password_label')}</label>
        <!-- minlength only when registering — login must accept older, shorter passwords. -->
        <input
          id="auth-password"
          class="input"
          type="password"
          bind:value={password}
          autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
          minlength={mode === 'register' ? PASSWORD_MIN_LENGTH : undefined}
        />
      </div>

      {#if mode === 'register'}
        <p class="pow ui" role="status">
          {#if powState === 'done'}<Icon name="check" size={14} /> {t('auth.pow_done')}{:else if powState === 'failed'}{t('auth.pow_failed')}{:else}{t('auth.pow_running')}{/if}
        </p>
        {#if !prefillHandle}
          <p class="hint">{t('auth.claim_hint')}</p>
        {/if}
      {/if}

      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}
      {#if pointer}
        <p class="pointer">
          <a href="/authors/{pointer.handle}" onclick={onDone}>
            {t('profile.auth_pointer_author_link')}
          </a>
          ·
          <a href="/activate?handle={pointer.handle}" onclick={onDone}>
            {t('profile.auth_pointer_claim_link')}
          </a>
        </p>
      {/if}

      <div class="actions">
        <button type="submit" class="btn btn-primary" disabled={busy}>
          {#if busy}{t('auth.wait')}{:else if mode === 'login'}{t('auth.login')}{:else}{t('auth.register')}{/if}
        </button>
        {#if mode === 'login'}
          <a class="forgot" href="/reset" onclick={onForgot}>{t('profile.auth_forgot_link')}</a>
        {/if}
      </div>
    </form>
  {/if}
</div>

<style>
  .tabs {
    display: flex;
    gap: var(--space-1);
    border-bottom: 1px solid var(--line);
    margin-bottom: var(--space-4);
  }

  .tab {
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--ink-3);
    cursor: pointer;
  }

  .tab[aria-selected='true'] {
    color: var(--ink);
    border-bottom-color: var(--accent);
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

  /* Honeypot: removed from sight and tab order, still in the DOM for bots. */
  .hp {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: var(--space-1) 0 0;
    line-height: 1.45;
  }

  form > .hint {
    margin: 0 0 var(--space-3);
  }

  .pow {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0 0 var(--space-3);
  }

  .claim {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  .claim-label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .registered .registered-h {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--ins-strong);
    margin: 0 0 var(--space-2);
  }

  .registered .registered-h.pending {
    color: var(--ink);
  }

  .registered .registered-body {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-3);
    line-height: 1.5;
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-3);
  }

  .pointer {
    font-size: var(--text-sm);
    margin: 0 0 var(--space-3);
  }

  .pointer a {
    color: var(--accent);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .forgot {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .forgot:hover {
    color: var(--accent);
  }
</style>
