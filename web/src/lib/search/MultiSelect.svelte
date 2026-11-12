<script lang="ts">
  /** Flervalsdropdown enligt v1:s formspråk (designkontraktets princip 6,
   * 2026-07-14): trigger i .input-stil + .card-baserad listbox-popover.
   * INGA checkboxar — vald rad markeras genom att hela raden färgas in
   * (accent-soft + accent, NG:s valda-idiom). Tangentbordsmodell per
   * guardrails §13: pil upp/ned, Home/End, Space/Enter växlar, Escape
   * stänger med fokus åter på triggern; klick utanför stänger. */
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';

  interface Item {
    value: string;
    label: string;
  }

  interface Props {
    items: Item[];
    selected: string[];
    placeholder: string;
    onchange: (next: string[]) => void;
  }

  let { items, selected, placeholder, onchange }: Props = $props();

  let open = $state(false);
  let focusedIndex = $state(-1);
  let rootEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLButtonElement | undefined = $state();
  let listEl: HTMLDivElement | undefined = $state();

  const triggerLabel = $derived(
    selected.length === 0
      ? placeholder
      : selected.length === 1
        ? (items.find((i) => i.value === selected[0])?.label ?? placeholder)
        : t('filters.n_selected', { count: selected.length })
  );

  function toggleOpen(): void {
    open = !open;
    if (open) {
      focusedIndex = -1;
      requestAnimationFrame(() => focusOption(0));
    }
  }

  function close(refocus = true): void {
    open = false;
    if (refocus) triggerEl?.focus();
  }

  function toggleItem(value: string): void {
    onchange(
      selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]
    );
  }

  function focusOption(index: number): void {
    const options = listEl?.querySelectorAll<HTMLElement>('[role="option"]');
    if (!options || options.length === 0) return;
    focusedIndex = Math.max(0, Math.min(index, options.length - 1));
    options[focusedIndex]?.focus();
  }

  function onTriggerKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) toggleOpen();
      else focusOption(0);
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      close();
    }
  }

  function onListKeydown(event: KeyboardEvent): void {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        focusOption(focusedIndex + 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        focusOption(focusedIndex - 1);
        break;
      case 'Home':
        event.preventDefault();
        focusOption(0);
        break;
      case 'End':
        event.preventDefault();
        focusOption(items.length - 1);
        break;
      case ' ':
      case 'Enter':
        event.preventDefault();
        if (focusedIndex >= 0 && items[focusedIndex]) toggleItem(items[focusedIndex].value);
        break;
      case 'Escape':
        event.preventDefault();
        close();
        break;
      case 'Tab':
        close(false);
        break;
    }
  }

  $effect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (rootEl && !rootEl.contains(event.target as Node)) close(false);
    };
    document.addEventListener('click', onDocClick, true);
    return () => document.removeEventListener('click', onDocClick, true);
  });
</script>

<div class="msd" bind:this={rootEl}>
  <button
    type="button"
    class="input trigger"
    class:active={selected.length > 0}
    bind:this={triggerEl}
    onclick={toggleOpen}
    onkeydown={onTriggerKeydown}
    aria-haspopup="listbox"
    aria-expanded={open}
  >
    <span class="tlabel">{triggerLabel}</span>
    {#if selected.length > 1}
      <span class="count-badge">{selected.length}</span>
    {/if}
    <span class="chev" class:open aria-hidden="true"><Icon name="chevron" size={14} /></span>
  </button>

  {#if open}
    <div
      class="panel card"
      bind:this={listEl}
      role="listbox"
      aria-multiselectable="true"
      aria-label={placeholder}
      tabindex="-1"
      onkeydown={onListKeydown}
    >
      {#each items as item, index (item.value)}
        <button
          type="button"
          class="option"
          role="option"
          aria-selected={selected.includes(item.value)}
          tabindex="-1"
          onclick={() => toggleItem(item.value)}
          onfocus={() => (focusedIndex = index)}
        >
          {item.label}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .msd {
    position: relative;
    display: inline-block;
  }

  .trigger {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    min-width: 11em;
    cursor: pointer;
    text-align: left;
  }

  .trigger.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  .tlabel {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chev {
    display: inline-flex;
    flex-shrink: 0;
    color: var(--ink-3);
    transition: transform 0.15s;
  }

  .chev.open {
    transform: rotate(180deg);
  }

  .panel {
    position: absolute;
    top: calc(100% + var(--space-1));
    left: 0;
    z-index: 40;
    min-width: 100%;
    max-height: 19em;
    overflow-y: auto;
    padding: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  /* Helradsmarkering — inga checkboxar (kontraktets princip 6). */
  .option {
    display: block;
    width: 100%;
    text-align: left;
    border: none;
    background: transparent;
    color: var(--ink);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s, color 0.15s;
  }

  .option:hover {
    background: var(--bg-sunken);
  }

  .option[aria-selected='true'] {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }
</style>
