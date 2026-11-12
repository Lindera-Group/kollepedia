<script lang="ts">
  import type { PillChange } from './script';

  interface Props {
    pills: PillChange[];
  }

  let { pills }: Props = $props();

  let root: HTMLElement | undefined = $state();
  let measured = $state(false);

  // Measure natural pill widths so appearing/disappearing pills reflow
  // their neighbours smoothly (same technique as AnimatedText).
  $effect(() => {
    void pills;
    if (!root) return;
    const wraps = root.querySelectorAll<HTMLElement>('.pillwrap');
    root.classList.add('measuring');
    const widths: number[] = [];
    wraps.forEach((w) => widths.push(w.getBoundingClientRect().width));
    wraps.forEach((w, i) => w.style.setProperty('--w', `${widths[i]}px`));
    root.classList.remove('measuring');
    measured = true;
  });

  const addedIndex = (i: number): number =>
    pills.slice(0, i).filter((p) => p.state === 'added').length;
</script>

<div class="pills ui" class:measuring={!measured} bind:this={root}>
  {#each pills as pill, i (pill.label + pill.state)}
    <span
      class="pillwrap {pill.state}"
      style={pill.state === 'added' ? `--pa:${Math.min(0.72 + addedIndex(i) * 0.09, 0.95)}` : ''}
    >
      <span class="pill tm-pill">{pill.label}</span>
    </span>
  {/each}
</div>

<style>
  .pills {
    display: flex;
    flex-wrap: wrap;
    min-height: 1.9em;
    align-items: center;
  }

  .pills.measuring .pillwrap {
    width: auto !important;
  }

  .pillwrap {
    display: inline-block;
    white-space: nowrap;
    padding-right: 0.5em;
  }

  /* Appearing pills zoom in from a point late on the master timeline (--pm). */
  .pillwrap.added {
    --ap: clamp(0, (var(--pm, 0) - var(--pa, 0.76)) / 0.16, 1);
    --ape: calc(var(--ap) * var(--ap) * (3 - 2 * var(--ap)));
    width: calc(var(--w, 0px) * var(--ape));
  }

  .pillwrap.added .tm-pill {
    transform: scale(var(--ape));
    opacity: var(--ape);
    border-color: var(--ins-strong);
    background-color: color-mix(
      in srgb,
      var(--ins-strong) calc((1 - var(--p4, 0)) * 14%),
      var(--bg-raised)
    );
  }

  /* Disappearing pills: red-marked early (--rm), zoom out to a point late (--rc). */
  .pillwrap.removed {
    --rm: clamp(0, (var(--pm, 0) - 0.05) / 0.1, 1);
    --rc: clamp(0, (var(--pm, 0) - 0.82) / 0.1, 1);
    --rce: calc(var(--rc) * var(--rc) * (3 - 2 * var(--rc)));
    width: calc(var(--w, 0px) * (1 - var(--rce)));
  }

  .pillwrap.removed .tm-pill {
    transform: scale(calc(1 - var(--rce)));
    opacity: calc(1 - var(--rce));
    border-color: color-mix(
      in srgb,
      var(--del-strong) calc(var(--rm) * 100%),
      var(--line)
    );
    background-color: color-mix(
      in srgb,
      var(--del-strong) calc(var(--rm) * (1 - var(--rce)) * 14%),
      var(--bg-raised)
    );
  }

  .tm-pill {
    display: inline-block;
    transform-origin: center;
  }

  /* Ink variant: no red/green — arriving pills in heavy ink, departing ones
     simply fade and collapse (colour-blind friendly, mirrors the text). */
  :global(.tm-stage.ink) .pillwrap.added .tm-pill {
    border-color: currentColor;
    background-color: var(--bg-raised);
    font-weight: 700;
  }

  :global(.tm-stage.ink) .pillwrap.removed .tm-pill {
    border-color: var(--line);
    background-color: var(--bg-raised);
  }
</style>
