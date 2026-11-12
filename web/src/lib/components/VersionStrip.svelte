<script lang="ts">
  /** Begreppssidans versionsremsa (2026-07-10): a mini-timeline of the MAIN
   * chronology — one dot per version, a gold ★ on the endorsed one, a faded
   * stub above dots where a branch forks off (branches themselves are never
   * drawn here — that's the history page's job). The whole strip is a
   * keyboard-operable "link" to the history page; each dot is a real button
   * that jumps straight to that version. `versions`/`forkIndices` are
   * computed by the caller (buildLanes in lib/timemachine/graph.ts) so the
   * "version X of Y" byline above can share the exact same chronology. */
  import { goto } from '$app/navigation';
  import type { VersionOut } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';
  import { hasActiveEndorsement } from '$lib/endorse/active';

  let {
    conceptId,
    versions,
    forkIndices = []
  }: {
    conceptId: string;
    versions: VersionOut[];
    forkIndices?: number[];
  } = $props();

  function historyHref(versionId?: string): string {
    return versionId
      ? `/concepts/${conceptId}/history?v=${versionId}`
      : `/concepts/${conceptId}/history`;
  }

  function openHistory(): void {
    void goto(historyHref());
  }

  // Keydown bubbles up from a focused dot button even though its own click
  // was already stopped there — only act when the STRIP itself has focus.
  function onStripKeydown(event: KeyboardEvent): void {
    if (event.target !== event.currentTarget) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openHistory();
    }
  }

  function openVersion(versionId: string, event: MouseEvent): void {
    event.stopPropagation();
    void goto(historyHref(versionId));
  }

  function dotLabel(version: VersionOut, index: number): string {
    const n = index + 1;
    return hasActiveEndorsement(version)
      ? t('cpage.strip_dot_endorsed', { n })
      : t('cpage.strip_dot', { n });
  }
</script>

<div
  class="vstrip ui"
  role="link"
  tabindex="0"
  aria-label={t('cpage.strip_aria', { n: versions.length })}
  onclick={openHistory}
  onkeydown={onStripKeydown}
>
  <span class="htitle">
    <Icon name="clock" size={16} />
    {t('hist.h1')}
  </span>
  <span class="rail">
    <span class="dots">
      {#each versions as version, i (version.id)}
        <button
          type="button"
          class="vdot"
          class:star={hasActiveEndorsement(version)}
          class:stub={forkIndices.includes(i)}
          title={dotLabel(version, i)}
          aria-label={dotLabel(version, i)}
          onclick={(event) => openVersion(version.id, event)}
        ></button>
      {/each}
    </span>
  </span>
  <span class="vcount mono"
    >{versions.length}
    {versions.length === 1 ? t('common.version_singular') : t('common.versions')}</span
  >
</div>

<style>
  .vstrip {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .vstrip:hover,
  .vstrip:focus-visible {
    border-color: var(--line-strong);
  }

  .htitle {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: 600;
    color: var(--ink);
    white-space: nowrap;
  }

  .rail {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 34px;
    display: flex;
    align-items: center;
    overflow-x: auto;
  }

  .dots {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    gap: var(--space-2);
    padding: 0 var(--space-1);
  }

  .dots::before {
    content: '';
    position: absolute;
    left: 4px;
    right: 4px;
    top: 50%;
    height: 2px;
    background: var(--accent);
    opacity: 0.85;
    transform: translateY(-50%);
  }

  .vdot {
    position: relative;
    flex: 0 0 auto;
    width: 11px;
    height: 11px;
    border-radius: var(--radius-round);
    background: var(--bg-raised);
    border: 2px solid var(--accent);
    padding: 0;
    cursor: pointer;
  }

  .vdot:hover,
  .vdot:focus-visible {
    background: var(--accent);
  }

  .vdot.star {
    border-color: var(--endorsed);
    background: var(--bg-raised);
  }

  .vdot.star::after {
    content: '★'; /* design-guard-exempt: dekorativ pseudo-element-stjärna = fastställd-semantiken, ej komponentbar */
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -54%);
    font-size: 8px; /* design-guard-exempt: viz micro-label below the type scale by design */
    color: var(--endorsed);
    line-height: 1;
  }

  .vdot.star:hover,
  .vdot.star:focus-visible {
    background: var(--bg-raised);
    box-shadow: 0 0 0 2px var(--endorsed);
  }

  /* Fade stub above a dot where a branch forks off the mainline — the
   * branch itself is never drawn here, only its point of departure. */
  .vdot.stub::before {
    content: '';
    position: absolute;
    left: 45%;
    top: -10px;
    width: 11px;
    height: 10px;
    border-left: 2px solid var(--ink-3);
    border-top: 2px solid var(--ink-3);
    border-top-left-radius: 10px 9px;
    mask-image: linear-gradient(to top right, #000 15%, transparent 80%); /* design-guard-exempt: mask alpha stop, not a color */
    -webkit-mask-image: linear-gradient(to top right, #000 15%, transparent 80%); /* design-guard-exempt: mask alpha stop, not a color */
  }

  .vcount {
    white-space: nowrap;
    color: var(--ink-3);
  }

  @media (prefers-reduced-motion: reduce) {
    .vstrip {
      transition-duration: 0.01ms;
    }
  }

  @media (max-width: 640px) {
    .vstrip {
      flex-wrap: wrap;
    }

    .rail {
      order: 3;
      flex-basis: 100%;
    }
  }
</style>
