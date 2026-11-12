<script lang="ts">
  import { t } from '$lib/i18n.svelte';
  import type { Transition } from './script';

  interface Props {
    transition: Transition;
  }

  let { transition }: Props = $props();

  let mode: 'before' | 'diff' | 'after' = $state('diff');

  const modes = $derived([
    ['before', t('sd.before')],
    ['diff', t('sd.changes')],
    ['after', t('sd.after')]
  ]);
</script>

<div class="staticdiff">
  <div class="modes ui" role="radiogroup" aria-label={t('sd.aria')}>
    {#each modes as [value, label] (value)}
      <button
        class="btn"
        class:btn-primary={mode === value}
        role="radio"
        aria-checked={mode === value}
        onclick={() => (mode = value as typeof mode)}>{label}</button
      >
    {/each}
  </div>

  <h1 class="title">
    {#each transition.title as s, i (i)}
      {#if (s.type === 'eq') || (s.type === 'del' && mode !== 'after') || (s.type === 'ins' && mode !== 'before')}
        <span class="s {s.type}" class:plain={mode !== 'diff'}>{s.text}</span>
      {/if}
    {/each}
  </h1>

  <p class="def">
    {#each transition.def as s, i (i)}
      {#if (s.type === 'eq') || (s.type === 'del' && mode !== 'after') || (s.type === 'ins' && mode !== 'before')}
        <span class="s {s.type}" class:plain={mode !== 'diff'}>{s.text}</span>
      {/if}
    {/each}
  </p>

  <p class="summary mono">
    {t('sd.summary', {
      ins: transition.insChars,
      del: transition.delChars,
      added: transition.pills.filter((p) => p.state === 'added').length,
      removed: transition.pills.filter((p) => p.state === 'removed').length
    })}
  </p>
</div>

<style>
  .staticdiff {
    padding: var(--space-4) 0;
  }

  .modes {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
  }

  .title {
    font-size: var(--text-2xl);
  }

  .def {
    font-size: var(--text-body-lg);
    max-width: 65ch;
    white-space: pre-wrap;
  }

  .s.del:not(.plain) {
    background: var(--del-wash);
    color: var(--del-strong);
    text-decoration: line-through;
    text-decoration-thickness: 1px;
    border-radius: var(--radius-sm);
  }

  .s.ins:not(.plain) {
    background: var(--ins-wash);
    box-shadow: inset 0 -2px 0 var(--ins-strong);
    border-radius: var(--radius-sm);
  }

  .summary {
    margin-top: var(--space-6);
    color: var(--ink-3);
  }
</style>
