<script lang="ts">
  import type { WordSpan } from './script';

  interface Props {
    spans: WordSpan[];
    blameA?: string[] | null;
    blameB?: string[] | null;
    agesA?: number[] | null;
    agesB?: number[] | null;
    restSide?: 'a' | 'b' | null;
    hoverVid?: string | null;
    /** Author id of the hovered token's version + vid→author lookup, for the
     * softer same-author tier (all text by the same person lights up). */
    hoverAuthorId?: string | null;
    authorByVid?: Map<string, string | null> | null;
    inkOn?: boolean;
    typedBreaks?: number;
    goneDelBreaks?: number;
    onhover?: (vid: string | null, event: MouseEvent | null) => void;
  }

  let {
    spans,
    blameA = null,
    blameB = null,
    agesA = null,
    agesB = null,
    restSide = null,
    hoverVid = null,
    hoverAuthorId = null,
    authorByVid = null,
    inkOn = false,
    typedBreaks = 0,
    goneDelBreaks = 0,
    onhover
  }: Props = $props();

  let root: HTMLElement | undefined = $state();
  let measured = $state(false);

  function measure(): void {
    if (!root) return;
    const words = root.querySelectorAll<HTMLElement>('.w.del, .w.ins');
    root.classList.add('measuring');
    const widths: number[] = [];
    words.forEach((w) => widths.push(w.getBoundingClientRect().width));
    words.forEach((w, i) => w.style.setProperty('--w', `${widths[i]}px`));
    root.classList.remove('measuring');
    measured = true;
  }

  // Measure synchronously after every span change (before paint — no flash),
  // and again once webfonts finish loading (fallback-font widths are wrong).
  // Ink mode changes font weights, hence widths — re-measure on toggle too.
  $effect(() => {
    void spans;
    void inkOn;
    measured = false;
    measure();
  });

  $effect(() => {
    let live = true;
    document.fonts?.ready.then(() => {
      if (live) measure();
    });
    return () => {
      live = false;
    };
  });

  function introVid(s: WordSpan): string | null {
    if (restSide === 'a') return s.aIdx !== null ? (blameA?.[s.aIdx] ?? null) : null;
    if (restSide === 'b') return s.bIdx !== null ? (blameB?.[s.bIdx] ?? null) : null;
    return null;
  }

  /** Ink ages come as A/B endpoints; CSS interpolates them over --pm so a
   * playing transition FADES between the two surrounding versions' ink
   * renderings (the chosen model). Steepened so one-version-old is visible. */
  function ageAOf(s: WordSpan): number {
    if (!inkOn) return 0;
    const raw = s.aIdx !== null ? (agesA?.[s.aIdx] ?? 0) : 0;
    return Math.pow(raw, 0.6);
  }

  function ageBOf(s: WordSpan): number {
    if (!inkOn) return 0;
    // Deleted words have no B side — hold their A age while they fade away.
    const raw = s.bIdx !== null ? (agesB?.[s.bIdx] ?? 0) : (s.aIdx !== null ? (agesA?.[s.aIdx] ?? 0) : 0);
    return Math.pow(raw, 0.6);
  }

  function sameAuthor(s: WordSpan): boolean {
    if (!hoverAuthorId || !authorByVid) return false;
    const vid = introVid(s);
    if (!vid || vid === hoverVid) return false;
    return authorByVid.get(vid) === hoverAuthorId;
  }

  function handleOver(event: MouseEvent): void {
    if (!onhover || restSide === null) return;
    const el = (event.target as HTMLElement).closest?.('.w') as HTMLElement | null;
    if (!el || !root?.contains(el)) return;
    const idx = Number(restSide === 'a' ? el.dataset.ai : el.dataset.bi);
    if (Number.isNaN(idx)) {
      onhover(null, null);
      return;
    }
    const blame = restSide === 'a' ? blameA : blameB;
    onhover(blame?.[idx] ?? null, event);
  }

  function handleOut(): void {
    onhover?.(null, null);
  }
</script>

<!-- Blame-on-hover is a pointer affordance; the same provenance is available
     without a pointer in the VersionTable below the stage. -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<span
  class="at"
  class:measuring={!measured}
  bind:this={root}
  onmouseover={handleOver}
  onmousemove={handleOver}
  onmouseleave={handleOut}
>
  {#each spans as s, i (i)}
    {#if s.kind === 'break'}
      <span
        class="br"
        class:off={(s.type === 'ins' && (s.breakOrdinal ?? 0) >= typedBreaks) ||
          (s.type === 'del' && (s.delBreakOrdinal ?? 0) < goneDelBreaks)}>{s.text}</span
      >
    {:else if s.type === 'eq'}
      <span
        class="w eq"
        data-ai={s.aIdx}
        data-bi={s.bIdx}
        class:hl={hoverVid !== null && introVid(s) === hoverVid}
        class:hl-author={sameAuthor(s)}
        style:--agea={ageAOf(s)}
        style:--ageb={ageBOf(s)}>{s.text}</span
      >
    {:else if s.type === 'del'}
      <span
        class="w del"
        data-ai={s.aIdx}
        class:hl={hoverVid !== null && introVid(s) === hoverVid}
        class:hl-author={sameAuthor(s)}
        style:--agea={ageAOf(s)}
        style:--ageb={ageBOf(s)}
        style="--ma:{s.ma};--ms:{s.ms};--ca:{s.ca};--cs:{s.cs}">{s.text}</span
      >
    {:else}
      <span
        class="w ins"
        data-bi={s.bIdx}
        class:hl={hoverVid !== null && introVid(s) === hoverVid}
        class:hl-author={sameAuthor(s)}
        style:--agea={ageAOf(s)}
        style:--ageb={ageBOf(s)}
        style="--a:{s.a};--span:{s.span};--len:{s.chars?.length}"
        >{#each s.chars ?? [] as c, ci (ci)}<span class="c" style="--ci:{ci}">{c}</span>{/each}</span
      >
    {/if}
  {/each}
</span>

<style>
  .at {
    display: inline;
  }

  .at.measuring :global(.w) {
    width: auto !important;
  }

  .br {
    white-space: pre-wrap;
  }

  .br.off {
    display: none;
  }

  .w {
    border-radius: var(--radius-sm);
    transition: background-color 0.2s;
    /* Effective ink age: fades from the outgoing version's age to the
       incoming one's as the transition progresses (--pm 0→1). */
    --age: calc(var(--agea, 0) + (var(--ageb, 0) - var(--agea, 0)) * var(--pm, 0));
  }

  .w.eq {
    white-space: pre-wrap;
  }

  /* Ink mode: the manuscript's geology on three channels at once —
     colour (ink → sepia), presence (opacity) and stroke weight (the serif
     is a variable font: fresh ink is heavy, old ink thin and faded). */
  :global(.tm-stage.ink) .w {
    color: color-mix(in oklab, currentColor calc(100% - var(--age, 0) * 82%), var(--sepia));
    opacity: calc(1 - var(--age, 0) * 0.34);
    font-weight: calc(650 - var(--age, 0) * 330);
    transition: color 0.4s, opacity 0.4s, font-weight 0.4s;
  }

  /* ── Deleted words ──
     Each word has its own mark window (--ma/--ms: red wash fades in, text
     greys) and collapse window (--ca/--cs: curtain closes) over the master
     progress --pm. Smoothstep (t²(3−2t)) eases both in pure calc(). */
  .w.del {
    display: inline-block;
    white-space: pre;
    overflow: hidden;
    vertical-align: bottom;
    --mp: clamp(0, (var(--pm, 0) - var(--ma, 0)) / var(--ms, 1), 1);
    --mpe: calc(var(--mp) * var(--mp) * (3 - 2 * var(--mp)));
    --cp: clamp(0, (var(--pm, 0) - var(--ca, 1)) / var(--cs, 1), 1);
    --cpe: calc(var(--cp) * var(--cp) * (3 - 2 * var(--cp)));
    width: calc(var(--w, 0px) * (1 - var(--cpe)));
    opacity: calc(1 - var(--cpe) * 0.9);
    color: color-mix(in oklab, currentColor calc(100% - var(--mpe) * 45%), var(--del-ink));
    background-color: color-mix(
      in srgb,
      var(--del-strong) calc(var(--mpe) * (1 - var(--cpe)) * 24%),
      transparent
    );
  }

  /* ── Inserted words: curtain opens just ahead of the typewriter, inside the
     word's own typing window (--a/--span) over --pm ── */
  .w.ins {
    display: inline-block;
    white-space: pre;
    overflow: hidden;
    vertical-align: bottom;
    position: relative;
    --lp: clamp(0, (var(--pm, 0) - var(--a, 0)) / var(--span, 1), 1);
    width: calc(var(--w, 0px) * min(1, var(--lp) * 1.1));
    background-color: color-mix(
      in srgb,
      var(--ins-strong) calc(min(1, var(--lp) * 6) * (1 - var(--p4, 0)) * 22%),
      transparent
    );
  }

  /* The caret: visible exactly while this word is being written (parabola). */
  .w.ins::after {
    content: '';
    position: absolute;
    right: 1px;
    top: 12%;
    bottom: 8%;
    width: 2px;
    background: var(--ins-strong);
    opacity: calc(var(--lp) * (1 - var(--lp)) * 4);
  }

  /* Blame hover: same version glows; the author's other text glows softer.
     MUST come after the del/ins background rules in the cascade — at rest
     their animated washes are zero but still won on source order, which made
     hover highlight only the eq words (the partial-highlight bug). Hover is
     only active at rest, so a flat override is safe. */
  .w.hl {
    background-color: var(--blame-wash);
  }

  .w.hl-author {
    background-color: color-mix(in srgb, var(--blame-wash) 45%, transparent);
  }

  .w.ins .c {
    opacity: clamp(0, calc(var(--lp) * var(--len, 1) - var(--ci, 0)), 1);
  }

  /* ── Ink variant of the transition (colour-free — colour-blind friendly):
     the SAME phase variables, rendered without red/green. Deletions fade
     toward nothing while marking, then collapse; insertions arrive in heavy
     fresh ink; ages keep rolling so older text visibly weathers. ── */
  :global(.tm-stage.ink) .w.del {
    background-color: transparent;
    color: currentColor;
    opacity: calc((1 - var(--mpe) * 0.75) * (1 - var(--cpe)));
  }

  :global(.tm-stage.ink) .w.ins {
    background-color: transparent;
    font-weight: 700;
  }

  :global(.tm-stage.ink) .w.ins::after {
    background: currentColor;
  }

  /* Hover washes must survive the ink variant's later background rules —
     the same cascade lesson as the colour mode (kept LAST on purpose). */
  :global(.tm-stage.ink) .w.hl,
  .w.hl {
    background-color: var(--blame-wash);
  }

  /* The author's OTHER edits: clearly weaker than the hovered edit — a faint
     wash plus a dotted underline (the colour-independent marker). */
  :global(.tm-stage.ink) .w.hl-author,
  .w.hl-author {
    background-color: color-mix(in srgb, var(--blame-wash) 22%, transparent);
    text-decoration: underline dotted;
    text-decoration-color: var(--ink-3);
    text-underline-offset: 0.2em;
  }

  /* Equal-height wash boxes: eq words are plain inline (short background box)
     while del/ins are inline-block at full line height — vertical padding on
     inline elements paints a taller box WITHOUT moving any lines, killing the
     ragged per-word mosaic (the reference screenshot). 1.75 line-height
     leaves 0.75em leading, so 0.28em top+bottom cannot overlap lines. */
  .w.eq.hl,
  .w.eq.hl-author {
    padding-top: 0.28em;
    padding-bottom: 0.28em;
  }
</style>
