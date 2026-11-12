<script lang="ts">
  /** Discreet contextual help: a small circled ?-button that opens an anchored
   * popover with a short explanation and a link into the manual (/manual).
   * Designed to be dropped inline anywhere without causing layout jumps. */
  import { i18n, t } from '$lib/i18n.svelte';
  import { helpTopics, type HelpTopicId } from './topics';

  interface Props {
    topic: HelpTopicId;
  }

  let { topic }: Props = $props();

  // Reads i18n.lang so the popover re-renders when the UI language switches.
  const topicData = $derived(helpTopics[i18n.lang][topic]);

  let open = $state(false);
  let root = $state<HTMLElement | undefined>();
  let trigger = $state<HTMLButtonElement | undefined>();
  let pop = $state<HTMLElement | undefined>();

  function toggle(): void {
    if (open) close(true);
    else open = true;
  }

  function close(refocus = false): void {
    if (!open) return;
    open = false;
    if (refocus) trigger?.focus();
  }

  // Focus the popover on open so Esc/blur behave and screen readers announce it.
  $effect(() => {
    if (open) pop?.focus();
  });

  function onWindowPointerDown(event: PointerEvent): void {
    if (!open) return;
    if (root && event.target instanceof Node && !root.contains(event.target)) close();
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (open && event.key === 'Escape') {
      event.preventDefault();
      close(true);
    }
  }

  function onFocusOut(event: FocusEvent): void {
    if (!open || !root) return;
    const next = event.relatedTarget;
    if (!(next instanceof Node) || !root.contains(next)) close();
  }
</script>

<svelte:window onpointerdown={onWindowPointerDown} onkeydown={onWindowKeydown} />

<span class="helptip ui" bind:this={root}>
  <button
    type="button"
    class="tip-btn"
    bind:this={trigger}
    onclick={toggle}
    onfocusout={onFocusOut}
    aria-label={t('helptip.aria', { title: topicData.title })}
    aria-expanded={open}
    aria-haspopup="dialog"
  >
    ?
  </button>

  {#if open}
    <span
      class="pop card"
      role="dialog"
      aria-label={t('helptip.aria', { title: topicData.title })}
      tabindex="-1"
      bind:this={pop}
      onfocusout={onFocusOut}
    >
      <span class="tip-title">{topicData.title}</span>
      <span class="tip-body">{topicData.body}</span>
      <a class="tip-more" href="/manual{topicData.anchor}">{t('helptip.read_more')}</a>
    </span>
  {/if}
</span>

<style>
  .helptip {
    position: relative;
    display: inline-flex;
    align-items: center;
    vertical-align: baseline;
    line-height: 1;
  }

  .tip-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.35em;
    height: 1.35em;
    padding: 0;
    border: 1px solid color-mix(in srgb, var(--ink-3) 55%, transparent);
    border-radius: var(--radius-round);
    background: transparent;
    color: var(--ink-3);
    font-family: var(--font-sans);
    font-size: 0.72em;
    font-weight: 600;
    line-height: 1;
    letter-spacing: 0;
    text-transform: none;
    cursor: help;
    transition: color 0.15s, border-color 0.15s, background-color 0.15s;
  }

  .tip-btn:hover,
  .tip-btn[aria-expanded='true'] {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .pop {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 50%;
    transform: translateX(-50%);
    z-index: 70;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    width: max-content;
    max-width: min(300px, 88vw);
    padding: var(--space-3) var(--space-4);
    box-shadow: var(--shadow-md);
    /* Reset context styling (tips may sit inside uppercase labels etc.) */
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 400;
    font-style: normal;
    letter-spacing: normal;
    text-transform: none;
    text-align: left;
    white-space: normal;
    line-height: 1.5;
    color: var(--ink);
    cursor: auto;
  }

  .pop:focus {
    outline: none;
  }

  .tip-title {
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--ink);
  }

  .tip-body {
    color: var(--ink-2);
  }

  .tip-more {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--accent);
    text-decoration: none;
  }

  .tip-more:hover {
    text-decoration: underline;
  }
</style>
