<script lang="ts">
  /** Account menu — account-only (signatures removed in the SPAM-hardening
   * pass). Two states:
   * - logged out → "Logga in" button opening login/register tabs (AuthForms),
   * - logged in → "▾ display_name" menu: Min profil / Min organisation / Logga ut.
   * Other components (the activity bell) can open the login form remotely via
   * requestLogin() — the authUi effect below picks the signal up. */
  import AuthForms from '$lib/auth/AuthForms.svelte';
  import { logout as apiLogout } from '$lib/api';
  import { t } from '$lib/i18n.svelte';
  import { authUi, clearSession, currentUser } from '$lib/user.svelte';

  let open = $state(false);
  let root: HTMLElement | undefined = $state();

  const loggedIn = $derived(currentUser.token !== null && currentUser.handle !== '');
  const pendingReview = $derived(currentUser.review_status === 'pending');

  // Remote login request (e.g. the activity bell when logged out).
  $effect(() => {
    if (authUi.requested) {
      authUi.requested = false;
      if (!loggedIn) open = true;
    }
  });

  function toggle(): void {
    open = !open;
  }

  function close(): void {
    open = false;
  }

  function logout(): void {
    // Best effort: revoke the refresh cookie server-side; local clear regardless.
    apiLogout().catch(() => {});
    clearSession();
    close();
  }

  function onDocumentClick(event: MouseEvent): void {
    if (open && root && !root.contains(event.target as Node)) close();
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && open) close();
  }
</script>

<svelte:document onclick={onDocumentClick} />
<svelte:window onkeydown={onWindowKeydown} />

<div class="userchip ui" bind:this={root}>
  <button
    class="chip"
    class:anonymous={!currentUser.handle}
    onclick={toggle}
    aria-expanded={open}
    aria-haspopup="dialog"
    title={loggedIn ? t('userchip.title_account_menu') : t('userchip.title_login')}
  >
    {#if currentUser.handle}
      <span class="dot" class:pending={pendingReview} aria-hidden="true"></span>
      <strong>{currentUser.display_name || currentUser.handle}</strong>
      <span class="caret" aria-hidden="true">▾</span>
    {:else}
      {t('auth.login')}
    {/if}
  </button>

  {#if open}
    <div class="popover card" role="dialog" aria-label={t('userchip.dialog_aria')}>
      {#if !loggedIn}
        <AuthForms onDone={close} />
      {:else}
        <p class="who">
          {t('userchip.logged_in_as')} <strong>{currentUser.handle}</strong
          >{#if currentUser.is_super_admin}&nbsp;· {t('userchip.super_admin')}{/if}{#if pendingReview}&nbsp;·
            {t('userchip.review_pending')}{/if}
        </p>
        <nav class="menu">
          <a class="item" href="/profile" onclick={close}>{t('profile.my_profile')}</a>
          <a class="item" href="/orgs" onclick={close}>{t('userchip.my_org')}</a>
          <button type="button" class="item" onclick={logout}>{t('userchip.logout')}</button>
        </nav>
      {/if}
    </div>
  {/if}
</div>

<style>
  .userchip {
    position: relative;
    display: inline-flex;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5em;
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 500;
    letter-spacing: 0.015em;
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    padding: 0.3em 0.9em;
    background: var(--bg-raised);
    color: var(--ink-2);
    cursor: pointer;
    transition:
      border-color 0.15s,
      color 0.15s;
  }

  .chip:hover {
    border-color: var(--ink);
    color: var(--ink);
  }

  .chip.anonymous {
    border-style: dashed;
    color: var(--ink-3);
  }

  .chip strong {
    color: var(--ink);
    max-width: 11rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Narrow screens: the header must always keep the hamburger reachable —
     truncate hard, then drop the name entirely (dot + caret still identify
     the account and its review state). */
  @media (max-width: 640px) {
    .chip strong {
      max-width: 5.5rem;
    }
  }

  @media (max-width: 460px) {
    .chip strong {
      display: none;
    }
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: var(--radius-round);
    background: var(--ins-strong);
    flex-shrink: 0;
  }

  .dot.pending {
    background: var(--ink-3);
  }

  .caret {
    font-size: 0.8em;
    color: var(--ink-3);
  }

  .popover {
    position: absolute;
    top: calc(100% + var(--space-2));
    right: 0;
    z-index: 60;
    width: 300px;
    padding: var(--space-4);
    box-shadow: var(--shadow-md);
  }

  .who {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0 0 var(--space-2);
  }

  .who strong {
    color: var(--ink);
  }

  .menu {
    display: flex;
    flex-direction: column;
  }

  .item {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: var(--space-2) var(--space-2);
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    color: var(--ink);
    text-decoration: none;
    cursor: pointer;
  }

  .item:hover {
    background: var(--bg);
  }
</style>
