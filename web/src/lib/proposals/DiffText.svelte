<script lang="ts">
  /** Static word-diff between two texts, sharing the Time Machine's visual
   * language (StaticDiff): red strike-through wash for deletions, green
   * underline wash for insertions. The mode is owned by the caller so one
   * radiogroup can drive several fields (name + definition). */
  import { diffText } from '$lib/timemachine/diff';

  interface Props {
    /** 'Före' — the target head (current main). */
    a: string;
    /** 'Efter' — the source head (the proposed branch). */
    b: string;
    mode: 'before' | 'diff' | 'after';
  }

  let { a, b, mode }: Props = $props();

  const ops = $derived(diffText(a, b));
</script>

<span class="dt">
  {#each ops as op, i (i)}
    {#if op.type === 'eq' || (op.type === 'del' && mode !== 'after') || (op.type === 'ins' && mode !== 'before')}
      <span class="s {op.type}" class:plain={mode !== 'diff'}
        >{op.tokens.map((token) => token.text).join('')}</span
      >
    {/if}
  {/each}
</span>

<style>
  .dt {
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
</style>
