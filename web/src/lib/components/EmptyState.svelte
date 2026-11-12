<script lang="ts">
  /** The shared soft state for anything that lacks content (plan
   * NG_ATTRIBUTION_OCH_FELHANTERING, paket D0) — zero search hits, a
   * resource that does not exist or is not public, an empty list.
   *
   * The contract (ui-guardrails §10, modelled on v1's empty-state-full):
   * say what is missing in a short serif message, then offer the LIKELY
   * NEXT STEP as an action — never a bare error code, never a blank area.
   *
   * `level` picks the heading element so a full-page soft state can carry
   * the page's h1 while an inline zero-hit state stays at h2/h3; sizes come
   * from the app.css heading globals. */
  import Icon from '$lib/icons/Icon.svelte';
  import type { IconName } from '$lib/icons/icons';
  import type { Snippet } from 'svelte';

  let {
    icon,
    heading,
    body,
    level = 2,
    actions,
    children
  }: {
    icon?: IconName;
    heading: string;
    /** Plain-text description; use `children` instead for rich content. */
    body?: string;
    level?: 1 | 2 | 3;
    /** Action row: buttons/links — the likely next step first. */
    actions?: Snippet;
    /** Rich body content (e.g. prose with inline links). */
    children?: Snippet;
  } = $props();
</script>

<div class="empty-state" role="status">
  {#if icon}
    <span class="es-icon"><Icon name={icon} size={44} /></span>
  {/if}
  <svelte:element this={`h${level}`} class="es-heading">{heading}</svelte:element>
  {#if body}
    <p class="es-body">{body}</p>
  {/if}
  {#if children}
    <div class="es-body">{@render children()}</div>
  {/if}
  {#if actions}
    <div class="es-actions ui">{@render actions()}</div>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-12) var(--space-6);
    text-align: center;
  }

  .es-icon {
    color: var(--ink-3);
    opacity: 0.6;
    margin-bottom: var(--space-4);
  }

  .es-heading {
    margin: 0 0 var(--space-2);
  }

  .es-body {
    font-family: var(--font-serif);
    font-size: var(--text-body-lg);
    color: var(--ink-2);
    max-width: 44ch;
    margin: 0 0 var(--space-4);
  }

  .es-body :global(p) {
    margin: 0;
  }

  .es-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: var(--space-3);
  }
</style>
