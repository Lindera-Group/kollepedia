<script lang="ts">
  import '@fontsource-variable/crimson-pro';
  import '@fontsource-variable/familjen-grotesk';
  import '@fontsource/fragment-mono';
  import '../app.css';
  import { tick } from 'svelte';
  import { browser } from '$app/environment';
  import { afterNavigate, goto } from '$app/navigation';
  import UserChip from '$lib/edit/UserChip.svelte';
  import { activityBell, refreshUnseen } from '$lib/activityBell.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { i18n, setLang, setLangForRender, t, type TranslationKey } from '$lib/i18n.svelte';
  import { cycleTheme, theme, type Theme } from '$lib/theme.svelte';
  import { currentUser, requestLogin } from '$lib/user.svelte';
  import { canSeeAdminHub } from '$lib/admin/adminNav';
  import { version as appVersion } from '../../package.json';

  let { children, data } = $props();

  // Server render only: pin the render language to the visitor's cookie so
  // SSR HTML — including {@html} content Svelte will not re-render on
  // hydration — matches the client. Component init runs inside the
  // synchronous render, so concurrent requests cannot interleave (a load
  // function could — see +layout.ts). Reading the initial prop value is
  // exactly the intent: data.lang never changes within one server render.
  // svelte-ignore state_referenced_locally
  if (!browser) setLangForRender(data.lang);

  const THEME_KEYS: Record<Theme, TranslationKey> = {
    light: 'theme.light',
    dark: 'theme.dark',
    contrast: 'theme.contrast'
  };
  const themeLabel = $derived(t(THEME_KEYS[theme.current]));
  const loggedIn = $derived(currentUser.token !== null && currentUser.handle !== '');

  // Grouped navigation. Ids are URLs and never translated; labels resolve
  // through t() so the menu is bilingual. Aktivitet lives in the header bell,
  // not here.
  type NavLink = { href: string; label: TranslationKey };
  const navGroups: { title: TranslationKey; links: NavLink[] }[] = [
    {
      title: 'nav.group_explore',
      links: [
        { href: '/', label: 'nav.search' },
        { href: '/collections', label: 'nav.collections' },
        { href: '/categories', label: 'nav.categories' },
        { href: '/authors', label: 'nav.authors' }
      ]
    },
    {
      title: 'nav.group_termwork',
      links: [
        { href: '/lists', label: 'nav.lists' },
        { href: '/compare', label: 'nav.compare' },
        { href: '/proposals', label: 'nav.proposals' }
      ]
    },
    {
      title: 'nav.group_about',
      links: [
        { href: '/manual', label: 'nav.manual' },
        { href: '/pricing', label: 'nav.create_account' },
        { href: '/about', label: 'nav.about' }
      ]
    }
  ];

  // The Administration group is appended to the menu only for admins
  // (superadmin OR any org-admin). It surfaces the single pedagogical hub at
  // /admin, making the otherwise unlinked admin/superadmin tools discoverable
  // from the menu. Reads currentUser (a rune) so it toggles on login/logout.
  const adminGroup: { title: TranslationKey; links: NavLink[] } = {
    title: 'nav.group_admin',
    links: [{ href: '/admin', label: 'nav.admin_hub' }]
  };
  const menuGroups = $derived(canSeeAdminHub() ? [...navGroups, adminGroup] : navGroups);

  let menuOpen = $state(false);
  let hamburger = $state<HTMLButtonElement | undefined>();
  let firstLink = $state<HTMLAnchorElement | undefined>();

  async function openMenu(): Promise<void> {
    menuOpen = true;
    await tick();
    firstLink?.focus();
  }

  function closeMenu(): void {
    if (!menuOpen) return;
    menuOpen = false;
    hamburger?.focus();
  }

  function toggleMenu(): void {
    if (menuOpen) closeMenu();
    else void openMenu();
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && menuOpen) closeMenu();
  }

  function onBellClick(): void {
    if (loggedIn) void goto('/activity');
    else requestLogin();
  }

  // Close after any client-side navigation (link click, back/forward).
  afterNavigate(() => {
    menuOpen = false;
    void refreshUnseen();
  });

  // Refresh the bell when the session appears/disappears.
  $effect(() => {
    if (browser && loggedIn) void refreshUnseen();
    else activityBell.unseen = 0;
  });
</script>

<svelte:window onkeydown={onWindowKeydown} />

<div class="shell">
  <a href="#main-content" class="skip-link">{t('a11y.skip_to_content')}</a>
  <header class="ui">
    <div class="container header-row">
      <a href="/" class="wordmark">Kollepedia <sup>NG</sup></a>

      <div class="header-controls">
        <button
          class="btn btn-quiet icon-btn"
          onclick={cycleTheme}
          title={t('theme.switch_title', { theme: themeLabel })}
          aria-label={t('theme.switch_aria', { theme: themeLabel })}
        >
          {#if theme.current === 'light'}
            <!-- Sol -->
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <circle cx="10" cy="10" r="4" fill="currentColor" />
              <g stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
                <path d="M10 1.5v2.2M10 16.3v2.2M1.5 10h2.2M16.3 10h2.2" />
                <path d="M4 4l1.55 1.55M14.45 14.45L16 16M16 4l-1.55 1.55M5.55 14.45L4 16" />
              </g>
            </svg>
          {:else if theme.current === 'dark'}
            <!-- Måne -->
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <path d="M16.5 12.6A7.4 7.4 0 0 1 7.4 3.5 7.4 7.4 0 1 0 16.5 12.6Z" fill="currentColor" />
            </svg>
          {:else}
            <!-- Högkontrast: halvfylld cirkel -->
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" stroke-width="1.8" />
              <path d="M10 2.5a7.5 7.5 0 0 1 0 15Z" fill="currentColor" />
            </svg>
          {/if}
        </button>

        <!-- Activity bell (Teams-style). Logged out: greyed, opens the login
             form. Logged in: goes to the personal activity feed; green +
             filled + count badge when there are unseen events. -->
        <button
          class="btn btn-quiet icon-btn bell"
          class:disabled={!loggedIn}
          class:unread={activityBell.unseen > 0}
          onclick={onBellClick}
          title={loggedIn ? t('nav.activity_bell_title') : t('nav.activity_bell_locked')}
          aria-label={loggedIn ? t('nav.activity_bell_title') : t('nav.activity_bell_locked')}
        >
          <Icon name="bell" filled={activityBell.unseen > 0} size={17} />
          {#if activityBell.unseen > 0}
            <span class="count-badge unread bell-count">{activityBell.unseen}</span>
          {/if}
        </button>

        <div class="lang-switch" role="group" aria-label={t('layout.lang_aria')}>
          <button
            class="lang-btn"
            aria-pressed={i18n.lang === 'sv'}
            title={t('layout.lang_sv_title')}
            onclick={() => setLang('sv')}
          >SV</button>
          <button
            class="lang-btn"
            aria-pressed={i18n.lang === 'en'}
            title={t('layout.lang_en_title')}
            onclick={() => setLang('en')}
          >EN</button>
        </div>

        <UserChip />

        <button
          class="hamburger"
          class:is-active={menuOpen}
          bind:this={hamburger}
          onclick={toggleMenu}
          aria-label={menuOpen ? t('nav.menu_close') : t('nav.menu_open')}
          aria-expanded={menuOpen}
          aria-controls="main-menu"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <line class="ham-line ham-top" x1="4" y1="6" x2="20" y2="6" />
            <line class="ham-line ham-mid" x1="4" y1="12" x2="20" y2="12" />
            <line class="ham-line ham-bot" x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  </header>

  <!-- Slide-in menu — always in the DOM so the close animation plays; inert
       (unfocusable, AT-hidden) while closed. Sits BELOW the sticky header in
       the stacking order so the hamburger stays visible as a ✕ and clickable
       while the menu is open. -->
  <div class="menu" class:is-open={menuOpen} id="main-menu" inert={!menuOpen}>
    <button class="menu-overlay" onclick={closeMenu} tabindex="-1" aria-label={t('nav.menu_close')}></button>
    <nav class="menu-panel" aria-label={t('nav.menu')}>
      {#each menuGroups as group, gi (group.title)}
        <div class="menu-group">
          <p class="menu-group-title mono">{t(group.title)}</p>
          <ul>
            {#each group.links as link (link.href)}
              <li>
                {#if gi === 0 && link.href === '/'}
                  <a bind:this={firstLink} href={link.href} onclick={closeMenu}>{t(link.label)}</a>
                {:else}
                  <a href={link.href} onclick={closeMenu}>{t(link.label)}</a>
                {/if}
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    </nav>
  </div>

  <main id="main-content">
    {@render children()}
  </main>

  <footer class="ui">
    <div class="container">
      <p>
        Kollepedia NG <span class="mono">v{appVersion}</span> ·
        <a href="/about">{t('footer.about_link')}</a> ·
        <a href="https://github.com/Lindera-Group/kollepedia" target="_blank" rel="noopener noreferrer"
          >{t('footer.open_source')}</a
        >
      </p>
    </div>
  </footer>
</div>

<style>
  .shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    backdrop-filter: blur(10px);
    position: sticky;
    top: 0;
    z-index: 50;
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    padding-top: var(--space-4);
    padding-bottom: var(--space-4);
  }

  .wordmark {
    font-family: var(--font-serif);
    font-size: var(--text-brand);
    font-weight: 600; /* gamla logotypsnittet – kontraktets princip 5 */
    color: var(--ink);
    text-decoration: none;
    letter-spacing: -0.01em;
    white-space: nowrap;
  }

  .wordmark sup {
    font-family: var(--font-mono);
    font-size: 0.5em;
    color: var(--accent);
    letter-spacing: 0.08em;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .bell {
    position: relative;
  }

  .bell.unread {
    color: var(--ins-strong);
  }

  .bell-count {
    position: absolute;
    top: -4px;
    right: -8px;
    font-size: var(--text-2xs);
    line-height: 1.3;
    padding: 0 0.4em;
  }

  .bell.disabled {
    color: var(--ink-3);
    opacity: 0.55;
  }

  .bell.disabled:hover {
    color: var(--ink-2);
    opacity: 0.8;
  }

  .lang-switch {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .lang-btn {
    border: none;
    background: transparent;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    letter-spacing: 0.04em;
    color: var(--ink-3);
    padding: 0.28em 0.7em;
    cursor: pointer;
    transition: color 0.15s, background-color 0.15s;
  }

  .lang-btn:hover {
    color: var(--ink);
  }

  .lang-btn[aria-pressed='true'] {
    background: var(--ink);
    color: var(--bg);
    cursor: default;
  }

  /* ── Hamburger button + line→X animation (from the original site) ── */
  .hamburger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    padding: 0;
    background: none;
    border: none;
    color: var(--ink);
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .hamburger:hover {
    color: var(--accent);
  }

  .hamburger:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: 2px;
  }

  .ham-line {
    transform-origin: 12px 12px;
    transition:
      transform 250ms cubic-bezier(0.4, 0, 0.2, 1),
      opacity 250ms cubic-bezier(0.4, 0, 0.2, 1);
  }

  .hamburger.is-active .ham-top {
    transform: rotate(45deg) translateY(6px);
  }

  .hamburger.is-active .ham-mid {
    opacity: 0;
    transform: scaleX(0);
  }

  .hamburger.is-active .ham-bot {
    transform: rotate(-45deg) translateY(-6px);
  }

  /* ── Slide-in menu ── */
  .menu {
    position: fixed;
    inset: 0;
    /* Below the sticky header (50): the header — and the hamburger's ✕ —
       stays visible and clickable above the overlay. */
    z-index: 40;
    pointer-events: none;
    visibility: hidden;
  }

  .menu.is-open {
    pointer-events: auto;
    visibility: visible;
  }

  .menu-overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: none;
    cursor: pointer;
    background: color-mix(in srgb, var(--ink) 34%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    opacity: 0;
    transition: opacity 250ms cubic-bezier(0.4, 0, 0.2, 1);
  }

  .menu.is-open .menu-overlay {
    opacity: 1;
  }

  .menu-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 300px;
    max-width: 82vw;
    background: var(--bg);
    border-left: 1px solid var(--line);
    box-shadow: -12px 0 40px -12px color-mix(in srgb, var(--ink) 30%, transparent);
    transform: translateX(100%);
    transition: transform 250ms cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    /* Clears the sticky header (taller since the larger wordmark). */
    padding: calc(var(--space-16) + var(--space-8)) var(--space-6) var(--space-8);
    overflow-y: auto;
  }

  .menu.is-open .menu-panel {
    transform: translateX(0);
  }

  .menu-group-title {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-3);
    margin-bottom: var(--space-2);
  }

  .menu-group ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .menu-group a {
    display: block;
    padding: var(--space-2) var(--space-3);
    margin: 0 calc(-1 * var(--space-3));
    color: var(--ink);
    text-decoration: none;
    font-size: var(--text-lg);
    font-family: var(--font-serif);
    border-radius: var(--radius-sm);
    border-right: 3px solid transparent;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
  }

  .menu-group a:hover {
    background: var(--bg-raised);
    border-right-color: var(--accent);
    color: var(--accent);
  }

  .menu-group a:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: -2px;
  }

  main {
    flex: 1;
    padding: var(--space-8) 0 var(--space-16);
  }

  footer {
    border-top: 1px solid var(--line);
    padding: var(--space-6) 0;
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  footer p {
    margin: 0;
  }

  @media (max-width: 460px) {
    .header-row {
      gap: var(--space-2);
    }

    .header-controls {
      gap: var(--space-2);
    }

    .wordmark {
      font-size: var(--text-base);
    }
  }
</style>
