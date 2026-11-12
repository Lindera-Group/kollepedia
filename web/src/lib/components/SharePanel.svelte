<script lang="ts">
  /** THE share surface (ui-guardrails §16): "Kopiera länk" opens a small
   * menu (same look as the Hantera gear menu) choosing between the living
   * concept link ("Alltid senaste version") and the PERMALÄNK pinned to this
   * exact version ("Låst till denna version"). External targets carry their
   * platform symbols. Used by the concept page's Dela subview AND the Time
   * Machine's version panel — one implementation, one look. */
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';

  interface Props {
    conceptId: string;
    versionId: string;
    /** Share text, e.g. "hållplats — Kollepedia NG". */
    title: string;
  }

  let { conceptId, versionId, title }: Props = $props();

  let menuOpen = $state(false);
  let copied = $state<'concept' | 'version' | null>(null);
  let copyTrigger = $state<HTMLButtonElement | undefined>();

  const conceptUrl = $derived(
    typeof location === 'undefined' ? '' : `${location.origin}/concepts/${conceptId}`
  );
  const versionUrl = $derived(
    typeof location === 'undefined' ? '' : `${location.origin}/versions/${versionId}`
  );

  async function copy(kind: 'concept' | 'version'): Promise<void> {
    menuOpen = false;
    copyTrigger?.focus();
    try {
      await navigator.clipboard.writeText(kind === 'version' ? versionUrl : conceptUrl);
      copied = kind;
      setTimeout(() => (copied = null), 2500);
    } catch {
      /* clipboard unavailable — the external targets still work */
    }
  }

  $effect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        menuOpen = false;
        copyTrigger?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.copy-wrap')) menuOpen = false;
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onClick);
    };
  });
</script>

<div class="share ui">
  <div class="subview-actions">
    <span class="copy-wrap">
      <button
        type="button"
        class="btn"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onclick={() => (menuOpen = !menuOpen)}
        bind:this={copyTrigger}
      >
        <Icon name="link" size={15} />
        {copied
          ? t('common.copied')
          : t('share.copy_link')}
      </button>
      {#if menuOpen}
        <div class="copy-menu card ui" role="menu" aria-label={t('share.copy_link')}>
          <button type="button" role="menuitem" onclick={() => copy('concept')}>
            <Icon name="link" size={14} />
            {t('share.link_latest')}
          </button>
          <button type="button" role="menuitem" onclick={() => copy('version')}>
            <Icon name="link" size={14} />
            {t('share.link_pinned')}
          </button>
        </div>
      {/if}
    </span>
    <a
      class="btn"
      href="mailto:?subject={encodeURIComponent(title)}&body={encodeURIComponent(conceptUrl)}"
    >
      <Icon name="mail" size={15} />
      {t('share.email')}
    </a>
    <a
      class="btn"
      href="https://www.linkedin.com/sharing/share-offsite/?url={encodeURIComponent(conceptUrl)}"
      target="_blank"
      rel="noopener noreferrer"
    >
      <Icon name="linkedin" size={15} />
      LinkedIn
    </a>
    <a
      class="btn"
      href="https://twitter.com/intent/tweet?url={encodeURIComponent(conceptUrl)}&text={encodeURIComponent(title)}"
      target="_blank"
      rel="noopener noreferrer"
    >
      <Icon name="xlogo" size={15} />
      X
    </a>
  </div>
  <p class="subview-hint hint-after">{t('share.hint_permalink')}</p>
</div>

<style>
  .copy-wrap {
    position: relative;
    display: inline-flex;
  }

  /* Same look as the Hantera gear menu (guardrails §16). */
  .copy-menu {
    position: absolute;
    z-index: 30;
    top: calc(100% + 6px);
    left: 0;
    min-width: 230px;
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
  }

  .copy-menu button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: none;
    background: transparent;
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
    border-radius: var(--radius-sm);
  }

  .copy-menu button:hover {
    background: var(--accent-soft);
  }

  .hint-after {
    margin: var(--space-3) 0 0;
  }
</style>
