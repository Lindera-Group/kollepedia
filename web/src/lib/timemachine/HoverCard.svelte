<script lang="ts">
  import type { VersionOut } from '$lib/api';
  import { formatDate, t } from '$lib/i18n.svelte';

  interface Props {
    version: VersionOut | null;
    x: number;
    y: number;
  }

  let { version, x, y }: Props = $props();

  const style = $derived.by(() => {
    const width = 300;
    // SSR guard: hover only happens in a browser, but keep the derived safe
    // if it is ever evaluated server-side.
    const viewport = typeof window === 'undefined' ? width + 24 : window.innerWidth;
    const left = Math.min(Math.max(12, x - width / 2), viewport - width - 12);
    const top = Math.max(12, y - 20);
    return `left:${left}px; top:${top}px; width:${width}px;`;
  });
</script>

{#if version}
  <div class="hovercard card ui" {style} role="tooltip">
    <p class="who">
      <strong>{version.created_by?.display_name ?? t('hc.unknown')}</strong>
      {#if version.created_by?.affiliation}
        <span class="aff">· {version.created_by.affiliation}</span>
      {/if}
    </p>
    <p class="when mono">{formatDate(version.created_at)}</p>
    {#if version.provenance?.kind === 'llm'}
      <p class="ai mono">{t('tm.ai_generated')} ({String(version.provenance.model ?? t('hc.unknown_model'))})</p>
    {/if}
    {#if version.note}
      <p class="note">”{version.note}”</p>
    {/if}
  </div>
{/if}

<style>
  .hovercard {
    position: fixed;
    z-index: 60;
    transform: translateY(-100%);
    padding: var(--space-3) var(--space-4);
    pointer-events: none;
    box-shadow: var(--shadow-md);
    animation: rise 0.15s var(--ease-out);
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 4px;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  .hovercard p {
    margin: 0 0 var(--space-1);
    font-size: var(--text-sm);
  }

  .who .aff {
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .when {
    color: var(--ink-3);
  }

  .ai {
    color: var(--accent);
  }

  .note {
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }
</style>
