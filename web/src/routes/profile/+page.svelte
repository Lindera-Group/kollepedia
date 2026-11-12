<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  /** Min profil (iteration 4): identity card, email with verification state,
   * password change. Email is set/changed via POST /auth/email which sends a
   * verification link — during testing all email stays in the admin outbox. */
  import { api, changePassword, night4, type AuthUser } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { PASSWORD_MIN_LENGTH, validateNewPassword } from '$lib/auth/password';
  import { t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';

  /** /auth/me extended with the night-4 email fields (optional until the
   * backend ships them — the UI degrades to "no email set"). */
  type MeOut = AuthUser & {
    email?: string | null;
    email_verified?: boolean;
    email_verified_at?: string | null;
  };

  const loggedIn = $derived(currentUser.token !== null && currentUser.handle !== '');

  let me = $state<MeOut | null>(null);
  let loadError = $state<string | null>(null);
  let loading = $state(true);
  // The public author surface 404s for accounts without visible authorship —
  // only link there when the page actually exists.
  let authorPageVisible = $state(false);

  $effect(() => {
    if (!loggedIn) {
      loading = false;
      return;
    }
    loading = true;
    api
      .me()
      .then((result) => {
        me = result as MeOut;
        return api.author(result.handle).then(
          () => (authorPageVisible = true),
          () => (authorPageVisible = false)
        );
      })
      .catch((e) => (loadError = errorMessage(e)))
      .finally(() => (loading = false));
  });

  // ── Public presentation (bio + URL, shown on the author page) ──
  let bioInput = $state('');
  let urlInput = $state('');
  let presBusy = $state(false);
  let presError = $state<string | null>(null);
  let presSaved = $state(false);
  let presSeeded = false;

  $effect(() => {
    if (me && !presSeeded) {
      presSeeded = true;
      bioInput = me.bio ?? '';
      urlInput = me.web_url ?? '';
    }
  });

  async function submitPresentation(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    presError = null;
    presSaved = false;
    presBusy = true;
    try {
      const updated = await api.patchMe({ bio: bioInput.trim(), web_url: urlInput.trim() });
      me = { ...me, ...updated } as MeOut;
      presSaved = true;
    } catch (e) {
      presError = t('profile.pres_error', {
        error: errorMessage(e)
      });
    } finally {
      presBusy = false;
    }
  }

  // ── Email ──
  let emailInput = $state('');
  let emailBusy = $state(false);
  let emailError = $state<string | null>(null);
  let emailSent = $state(false);

  async function submitEmail(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    emailError = null;
    emailSent = false;
    const email = emailInput.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      emailError = t('profile.email_invalid');
      return;
    }
    emailBusy = true;
    try {
      await night4.setEmail(email);
      if (me) me = { ...me, email, email_verified: false };
      emailInput = '';
      emailSent = true;
    } catch (e) {
      emailError = t('profile.email_error', {
        error: errorMessage(e)
      });
    } finally {
      emailBusy = false;
    }
  }

  // ── Password ──
  let pwCurrent = $state('');
  let pwNew = $state('');
  let pwConfirm = $state('');
  let pwBusy = $state(false);
  let pwError = $state<string | null>(null);
  let pwChanged = $state(false);

  async function submitPassword(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    pwError = null;
    pwChanged = false;
    if (!pwCurrent || !pwNew) {
      pwError = t('profile.pw_missing');
      return;
    }
    pwError = validateNewPassword(pwNew, pwConfirm);
    if (pwError) return;
    pwBusy = true;
    try {
      await changePassword({ current_password: pwCurrent, new_password: pwNew });
      pwCurrent = '';
      pwNew = '';
      pwConfirm = '';
      pwChanged = true;
    } catch (e) {
      pwError = t('profile.pw_error', { error: errorMessage(e) });
    } finally {
      pwBusy = false;
    }
  }

  function roleLabel(role: string): string {
    if (role === 'admin') return t('orgs.role_admin');
    if (role === 'editor') return t('orgs.role_editor');
    if (role === 'viewer') return t('orgs.role_viewer');
    return role;
  }
</script>

<svelte:head><title>{t('profile.head_title')}</title></svelte:head>

<div class="container narrow">
  {#if !loggedIn}
    <div class="card guard ui">
      <h1>{t('profile.h1')}</h1>
      <p>{t('profile.guard_body')}</p>
      <p><a href="/">{t('common.to_home')}</a></p>
    </div>
  {:else}
    <PageHeader title={me?.display_name ?? currentUser.display_name} />

    {#if loading}
      <p class="ui muted">{t('profile.loading')}</p>
    {:else if loadError}
      <p class="error ui" role="alert">{t('profile.load_error', { error: loadError })}</p>
    {:else if me}
      <!-- ── Identity ── -->
      <section class="card ui block" aria-labelledby="profile-identity">
        <h2 id="profile-identity" class="sr-only">{t('profile.h1')}</h2>
        <dl class="facts">
          <div>
            <dt>{t('profile.handle_label')}</dt>
            <dd class="mono">{me.handle}</dd>
          </div>
          <div>
            <dt>{t('auth.display_name_label')}</dt>
            <dd>
              {me.display_name}
              {#if me.is_super_admin}
                <span class="pill super">{t('userchip.super_admin')}</span>
              {/if}
            </dd>
          </div>
          <div>
            <dt>{t('profile.affiliation_label')}</dt>
            <dd>{me.affiliation ?? t('typo.dash')}</dd>
          </div>
          <div>
            <dt>{t('profile.org_label')}</dt>
            <dd>
              {#if me.memberships.length}
                {#each me.memberships as membership (membership.id)}
                  <span class="membership">
                    <a href="/orgs">{membership.name}</a>
                    <span class="muted"
                      >· {roleLabel(membership.role)}{membership.kind === 'guest'
                        ? ` · ${t('orgs.kind_guest')}`
                        : ''}{membership.is_owner ? ` · ${t('orgs.owner_pill')}` : ''}</span
                    >
                  </span>
                {/each}
              {:else}
                {t('profile.no_org')}
              {/if}
            </dd>
          </div>
        </dl>
        <p class="author-link">
          {#if authorPageVisible}
            <a href="/authors/{me.handle}">{t('profile.author_page_link')}</a>
          {:else}
            <span class="muted">{t('profile.author_page_pending')}</span>
          {/if}
        </p>
      </section>

      <!-- ── Email ── -->
      <section class="card ui block" aria-labelledby="profile-presentation">
        <h2 id="profile-presentation">{t('profile.pres_h2')}</h2>
        <p class="fine pres-hint">{t('profile.pres_hint')}</p>
        <form onsubmit={submitPresentation} aria-label={t('profile.pres_h2')}>
          <div class="field">
            <label for="profile-bio">{t('profile.bio_label')}</label>
            <textarea
              id="profile-bio"
              class="input"
              rows="3"
              bind:value={bioInput}
              placeholder={t('profile.bio_placeholder')}
              disabled={presBusy}
            ></textarea>
          </div>
          <div class="field">
            <label for="profile-url">{t('profile.url_label')}</label>
            <input
              id="profile-url"
              class="input"
              type="url"
              bind:value={urlInput}
              placeholder={t('profile.url_placeholder')}
              disabled={presBusy}
              spellcheck="false"
            />
          </div>
          {#if presError}<p class="error" role="alert">{presError}</p>{/if}
          {#if presSaved}<p class="success" role="status">{t('profile.pres_saved')}</p>{/if}
          <button type="submit" class="btn btn-primary" disabled={presBusy}>
            {presBusy ? t('common.saving') : t('profile.pres_save')}
          </button>
        </form>
      </section>

      <section class="card ui block" aria-labelledby="profile-email">
        <h2 id="profile-email">{t('profile.email_h2')}</h2>
        <p class="current">
          <span class="label">{t('profile.email_current_label')}</span>
          {#if me.email}
            <span class="mono">{me.email}</span>
            {#if me.email_verified}
              <span class="pill verified"><Icon name="check" size={14} /> {t('profile.email_verified')}</span>
            {:else}
              <span class="pill unverified">{t('profile.email_unverified')}</span>
            {/if}
          {:else}
            <span class="muted">{t('profile.email_none')}</span>
          {/if}
        </p>

        <form onsubmit={submitEmail} aria-label={me.email ? t('profile.email_change_legend') : t('profile.email_set_legend')}>
          <div class="field">
            <label for="profile-email-input">
              {me.email ? t('profile.email_change_legend') : t('profile.email_set_legend')}
            </label>
            <input
              id="profile-email-input"
              class="input"
              type="email"
              bind:value={emailInput}
              placeholder={t('profile.auth_email_placeholder')}
              autocomplete="email"
              disabled={emailBusy}
            />
          </div>
          {#if emailError}
            <p class="error" role="alert">{emailError}</p>
          {/if}
          {#if emailSent}
            <p class="success" role="status"><Icon name="check" size={14} /> {t('profile.email_sent')}</p>
          {/if}
          <div class="actions">
            <button type="submit" class="btn btn-primary" disabled={emailBusy || !emailInput.trim()}>
              {emailBusy ? t('common.saving') : t('profile.email_save')}
            </button>
          </div>
          <p class="fine">{t('profile.email_reverify_hint')}</p>
        </form>
      </section>

      <!-- ── Password ── -->
      <section class="card ui block" aria-labelledby="profile-password">
        <h2 id="profile-password">{t('profile.pw_h2')}</h2>
        <form onsubmit={submitPassword} aria-label={t('profile.pw_h2')}>
          <div class="field">
            <label for="profile-pw-current">{t('profile.pw_current')}</label>
            <input
              id="profile-pw-current"
              class="input"
              type="password"
              bind:value={pwCurrent}
              autocomplete="current-password"
              disabled={pwBusy}
            />
          </div>
          <div class="field">
            <label for="profile-pw-new">{t('profile.pw_new')}</label>
            <input
              id="profile-pw-new"
              class="input"
              type="password"
              bind:value={pwNew}
              autocomplete="new-password"
              minlength={PASSWORD_MIN_LENGTH}
              disabled={pwBusy}
            />
          </div>
          <div class="field">
            <label for="profile-pw-confirm">{t('rst.repeat')}</label>
            <input
              id="profile-pw-confirm"
              class="input"
              type="password"
              bind:value={pwConfirm}
              autocomplete="new-password"
              minlength={PASSWORD_MIN_LENGTH}
              disabled={pwBusy}
            />
          </div>
          {#if pwError}
            <p class="error" role="alert">{pwError}</p>
          {/if}
          {#if pwChanged}
            <p class="success" role="status"><Icon name="check" size={14} /> {t('profile.pw_changed')}</p>
          {/if}
          <div class="actions">
            <button type="submit" class="btn btn-primary" disabled={pwBusy}>
              {pwBusy ? t('common.saving') : t('profile.pw_change')}
            </button>
          </div>
        </form>
      </section>
    {/if}
  {/if}
</div>

<style>

  .block {
    margin-bottom: var(--space-6);
  }

  .block h2 {
    margin-bottom: var(--space-4);
  }

  .facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--space-4);
    margin: 0 0 var(--space-4);
  }

  .facts dt {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .facts dd {
    margin: 0;
    font-size: var(--text-base);
  }

  .author-link {
    margin: 0;
    font-size: var(--text-sm);
  }

  .current {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
  }

  .current .label {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .verified {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .unverified {
    border-style: dashed;
    border-color: var(--ink-3);
    color: var(--ink-3);
  }

  .super {
    border-color: var(--endorsed);
    color: var(--endorsed);
    margin-left: var(--space-1);
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

  input,
  textarea {
    width: 100%;
  }

  .pres-hint {
    margin-bottom: var(--space-3);
  }

  .field {
    margin-bottom: var(--space-3);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .fine {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0;
    line-height: 1.5;
  }

  .success {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin: 0 0 var(--space-3);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: 0 0 var(--space-3);
  }

  .membership {
    display: block;
  }

  .muted {
    color: var(--ink-3);
  }

</style>
