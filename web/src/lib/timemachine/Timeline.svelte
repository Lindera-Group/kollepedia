<script lang="ts">
  import type { VersionOut } from '$lib/api';
  import { fullLanePath, type Lane, type LaneModel } from './graph';
  import type { Playback } from './playback.svelte';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { hasActiveEndorsement } from '$lib/endorse/active';

  interface Props {
    engine: Playback;
    lanes: LaneModel;
    branchName: string;
    onSelectBranch: (name: string, anchorId: string) => void;
  }

  let { engine, lanes, branchName, onSelectBranch }: Props = $props();

  let trackEl: HTMLElement | undefined = $state();
  let trackWidth = $state(0);
  /** Hover preview: the lane (by name, 'main' included) under the pointer. */
  let hoveredLane = $state<string | null>(null);

  const uid = $props.id();

  /** Track geometry. The playhead knob spans y 8–22 (8px top offset + 14px
   * knob). The TOPMOST lane row always lands at y = BASE_RAIL_Y, because
   * railY − maxRow·gap = BASE_RAIL_Y regardless of lane count or gap — so
   * with 12px on-path dots (radius 6) the knob clearance is a constant
   * 34 − 6 − 22 = 6px. Below the rail, BASE_HEIGHT − BASE_RAIL_Y = 35px
   * carries the year labels. Worked example, 3 lanes at trackWidth < 480
   * (12px gap): height 69+36 = 105, rail at y 70, lanes at 58/46/34. */
  const PAD = 18;
  const BASE_HEIGHT = 69;
  const BASE_RAIL_Y = 34;

  const laneCount = $derived(lanes.lanes.length);
  /** Lane spacing compresses on narrow tracks (mobile). */
  const laneGap = $derived(trackWidth > 0 && trackWidth < 480 ? 12 : 16);
  /** Highest occupied lane row (rows are unique, so this is laneCount too). */
  const maxRow = $derived(lanes.lanes.reduce((m, l) => Math.max(m, l.row), 0));
  /** Lanes stack ABOVE the rail; the track grows upward to make room. */
  const trackHeight = $derived(BASE_HEIGHT + maxRow * laneGap);
  const railY = $derived(BASE_RAIL_Y + maxRow * laneGap);

  function yOfRow(row: number): number {
    return railY - row * laneGap;
  }

  const laneByName = $derived(new Map(lanes.lanes.map((l) => [l.name, l])));

  /** Parent chain of the selected branch, outermost (forks from main) first.
   * Empty when main (or an unresolvable branch) is selected. */
  const selectedChain = $derived.by((): Lane[] => {
    const chain: Lane[] = [];
    const guard = new Set<string>();
    let cursor = laneByName.get(branchName);
    while (cursor && !guard.has(cursor.name)) {
      guard.add(cursor.name);
      chain.unshift(cursor);
      cursor = cursor.parent === 'main' ? undefined : laneByName.get(cursor.parent);
    }
    return chain;
  });

  /** Path index (into engine.versions) where each chain lane's own versions
   * begin: the outermost lane starts right after its fork on the trunk; a
   * deeper lane right after its fork inside the parent's segment. */
  const chainStarts = $derived.by(() => {
    let prev = 0;
    return selectedChain.map((lane, j) => {
      prev = (j === 0 ? lane.forkIndex : prev + lane.forkIndex) + 1;
      return prev;
    });
  });

  /** Every rendered version (trunk + lanes + the engine's path as a safety
   * net for off-trunk selections), deduplicated and time-ordered — the
   * shared time scale spans the union of all of them. */
  const allVersions = $derived.by(() => {
    const seen = new Set<string>();
    const union: VersionOut[] = [];
    const sources = [...lanes.mainPath, ...lanes.lanes.flatMap((l) => l.versions), ...engine.versions];
    for (const v of sources) {
      if (!seen.has(v.id)) {
        seen.add(v.id);
        union.push(v);
      }
    }
    return union.sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
  });

  /** Fraction (0..1) per version id: proportional to real time, with a
   * minimum visual gap, computed over the whole union so main and branch
   * dots share one scale (and one nudging pass). */
  const fracById = $derived.by(() => {
    const versions = allVersions;
    if (versions.length === 0) return new Map<string, number>();
    if (versions.length === 1) return new Map([[versions[0].id, 0.5]]);
    const times = versions.map((v) => new Date(v.created_at).getTime());
    const t0 = times[0];
    const spanT = Math.max(1, times[times.length - 1] - t0);
    const raw = times.map((time) => (time - t0) / spanT);
    const minGap = Math.min(0.08, 1 / (versions.length + 2));
    for (let i = 1; i < raw.length; i++) {
      if (raw[i] - raw[i - 1] < minGap) raw[i] = raw[i - 1] + minGap;
    }
    const max = raw[raw.length - 1];
    return new Map(versions.map((v, i) => [v.id, raw[i] / max]));
  });

  /** Fractions along the SELECTED path — the engine's position axis. */
  const fracs = $derived(engine.versions.map((v) => fracById.get(v.id) ?? 0.5));

  function xOfFrac(frac: number): number {
    return PAD + frac * (trackWidth - PAD * 2);
  }

  function xOf(position: number): number {
    const i = Math.min(Math.floor(position), fracs.length - 2);
    if (fracs.length === 1 || i < 0) return xOfFrac(fracs[0] ?? 0.5);
    const f = position - i;
    return xOfFrac(fracs[i] + (fracs[i + 1] - fracs[i]) * f);
  }

  function positionFromX(clientX: number): number {
    if (!trackEl) return 0;
    const rect = trackEl.getBoundingClientRect();
    const usable = rect.width - PAD * 2;
    const frac = Math.min(1, Math.max(0, (clientX - rect.left - PAD) / usable));
    // Invert the piecewise-linear dot mapping.
    for (let i = 0; i < fracs.length - 1; i++) {
      if (frac <= fracs[i + 1]) {
        const segment = fracs[i + 1] - fracs[i];
        return i + (segment > 0 ? Math.min(1, Math.max(0, (frac - fracs[i]) / segment)) : 0);
      }
    }
    return fracs.length - 1;
  }

  /** Y of the i-th version on the selected path: the trunk until the
   * outermost fork, then each lane of the parent chain in turn. */
  function yOfPathIndex(i: number): number {
    let y = railY;
    for (let j = 0; j < selectedChain.length; j++) {
      if (i >= chainStarts[j]) y = yOfRow(selectedChain[j].row);
    }
    return y;
  }

  /** Dots NOT on the selected path: branch-lane dots plus (when a branch is
   * selected) the mainline's remainder — clicking one switches the path. */
  const offPathDots = $derived.by(() => {
    const onPath = new Set(engine.versions.map((v) => v.id));
    const dots: { laneName: string; version: VersionOut; frac: number; y: number }[] = [];
    for (const lane of lanes.lanes) {
      for (const v of lane.versions) {
        if (onPath.has(v.id)) continue;
        dots.push({
          laneName: lane.name,
          version: v,
          frac: fracById.get(v.id) ?? 0.5,
          y: yOfRow(lane.row)
        });
      }
    }
    for (const v of lanes.mainPath) {
      if (!onPath.has(v.id)) {
        dots.push({ laneName: 'main', version: v, frac: fracById.get(v.id) ?? 0.5, y: railY });
      }
    }
    return dots;
  });

  /** Gentle git-graph cubic from the fork up to the lane. */
  function curveTo(x1: number, y1: number, x2: number, y2: number): string {
    const dx = Math.max(8, Math.min(28, (x2 - x1) * 0.6));
    return `C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  }

  /** A lane's line: a curve leaving the PARENT lane's y at the fork x (the
   * trunk for top-level lanes, the parent lane's row for nested ones), then
   * a horizontal run along the lane's own row. */
  function lanePathD(lane: Lane): string {
    const parentLane = lane.parent === 'main' ? undefined : laneByName.get(lane.parent);
    const parentY = parentLane ? yOfRow(parentLane.row) : railY;
    const forkVersion = parentLane
      ? parentLane.versions[lane.forkIndex]
      : lanes.mainPath[lane.forkIndex];
    const laneY = yOfRow(lane.row);
    const xFork = xOfFrac(fracById.get(forkVersion?.id ?? '') ?? 0.5);
    const xFirst = xOfFrac(fracById.get(lane.versions[0].id) ?? 0.5);
    const xLast = xOfFrac(fracById.get(lane.versions[lane.versions.length - 1].id) ?? 0.5);
    let d = `M ${xFork} ${parentY} ${curveTo(xFork, parentY, xFirst, laneY)}`;
    if (xLast > xFirst) d += ` L ${xLast} ${laneY}`;
    return d;
  }

  /** Mainline rail extent (the trunk). */
  const railX = $derived.by(() => {
    const path = lanes.mainPath;
    if (path.length === 0) return { x1: PAD, x2: trackWidth - PAD };
    return {
      x1: xOfFrac(fracById.get(path[0].id) ?? 0),
      x2: xOfFrac(fracById.get(path[path.length - 1].id) ?? 1)
    };
  });

  /** The selected path as one thick stroke: along the trunk, then a curve
   * into EACH lane of the parent chain — a nested selection walks main →
   * parent lane → child lane (or just the rail when main is selected). */
  const selectedPathD = $derived.by(() => {
    if (engine.versions.length === 0) return '';
    const x0 = xOf(0);
    const xEnd = xOf(engine.versions.length - 1);
    if (selectedChain.length === 0) return `M ${x0} ${railY} L ${Math.max(xEnd, x0 + 0.01)} ${railY}`;
    let d = `M ${x0} ${railY}`;
    let y = railY;
    let xCursor = x0;
    selectedChain.forEach((lane, j) => {
      const xFork = xOf(chainStarts[j] - 1);
      const xFirst = xOf(chainStarts[j]);
      const laneY = yOfRow(lane.row);
      d += ` L ${xFork} ${y} ${curveTo(xFork, y, xFirst, laneY)}`;
      y = laneY;
      xCursor = xFirst;
    });
    if (xEnd > xCursor) d += ` L ${xEnd} ${y}`;
    return d;
  });

  let dragging = $state(false);

  function onPointerDown(event: PointerEvent): void {
    engine.pause();
    dragging = true;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    engine.seek(positionFromX(event.clientX));
  }

  function onPointerMove(event: PointerEvent): void {
    if (dragging) engine.seek(positionFromX(event.clientX));
  }

  function onPointerUp(): void {
    dragging = false;
  }

  function selectLane(name: string, anchorId: string): void {
    engine.pause();
    hoveredLane = null;
    onSelectBranch(name, anchorId);
  }

  /** Index in engine.versions of the last version shared with `path` — the
   * point where the current path and a candidate path diverge. */
  function divergenceIndex(path: VersionOut[]): number {
    const idIndex = new Map(engine.versions.map((v, i) => [v.id, i]));
    let last = -1;
    for (const v of path) {
      const i = idIndex.get(v.id);
      if (i !== undefined && i > last) last = i;
    }
    return last;
  }

  /** ↑/↓ on the playhead: switch path at the current position. Cyclable
   * (row order, main first) are the trunk and every lane — nested ones
   * included — whose divergence from the CURRENT path has been passed;
   * the anchor is the shared divergence version so the position stays
   * meaningful. */
  function switchPath(dir: 1 | -1): void {
    const pos = Math.round(engine.position);
    const order = ['main'];
    for (const lane of lanes.lanes) {
      if (lane.name === branchName) {
        order.push(lane.name); // the current path is always in its own cycle
        continue;
      }
      const d = divergenceIndex(fullLanePath(lanes, lane.name));
      if (d >= 0 && d <= pos) order.push(lane.name);
    }
    if (order.length < 2) return;
    let current = order.indexOf(branchName);
    if (current === -1) {
      // On a path outside the cycle (unresolvable branch):
      // ↓ returns to main, ↑ takes the first available lane.
      current = dir === 1 ? 0 : 1;
    }
    const next = Math.min(order.length - 1, Math.max(0, current + dir));
    if (next === current) return;
    const target = order[next];
    const anchorId = anchorForSwitch(target, pos);
    if (anchorId) selectLane(target, anchorId);
  }

  function anchorForSwitch(target: string, pos: number): string | null {
    const path = fullLanePath(lanes, target);
    if (target === 'main') {
      // Already standing on a trunk version → stay put.
      const focus = engine.versions[Math.min(pos, engine.versions.length - 1)];
      if (focus && lanes.mainPath.some((v) => v.id === focus.id)) return focus.id;
    }
    const d = divergenceIndex(path);
    if (d >= 0) return engine.versions[d].id;
    return path[0]?.id ?? null;
  }

  /** Main-rail click/keyboard: return to the trunk, landing where the
   * selected chain's OUTERMOST fork left it (where the paths diverged). */
  function selectMain(): void {
    const outer = selectedChain[0];
    const anchorId =
      (outer ? (lanes.mainPath[outer.forkIndex]?.id ?? null) : null) ??
      anchorForSwitch('main', Math.round(engine.position));
    if (anchorId) selectLane('main', anchorId);
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      if (event.shiftKey) engine.seek(engine.position + 0.03);
      else engine.stepForward();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      if (event.shiftKey) engine.seek(engine.position - 0.03);
      else engine.stepBack();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      switchPath(1);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      switchPath(-1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      engine.pause();
      engine.seek(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      engine.pause();
      engine.seek(engine.maxPosition);
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      engine.toggle();
    }
  }

  const valueText = $derived.by(() => {
    const i = engine.focusIndex;
    const version = engine.versions[i];
    if (!version) return '';
    const base = `${t('tm.version_x_of_y', { x: i + 1, y: engine.versions.length })} · ${formatDate(version.created_at)}`;
    if (laneCount === 0) return base;
    const path =
      branchName === 'main' ? t('tl.path_main') : t('tl.path_branch', { name: branchName });
    return `${base} · ${path}`;
  });

  /** Sparse year labels over the shared time scale: first of each year. */
  const yearLabels = $derived.by(() => {
    const labels: { id: string; frac: number; year: string }[] = [];
    let previous = '';
    for (const v of allVersions) {
      const year = String(new Date(v.created_at).getFullYear());
      if (year !== previous) {
        labels.push({ id: v.id, frac: fracById.get(v.id) ?? 0.5, year });
        previous = year;
      }
    }
    return labels;
  });

  /** Thin labels to what the track width can carry (mobile!). */
  const visibleYearLabels = $derived.by(() => {
    const max = Math.max(2, Math.floor(trackWidth / 80));
    if (yearLabels.length <= max) return yearLabels;
    const picked = [yearLabels[0]];
    const step = (yearLabels.length - 1) / (max - 1);
    for (let i = 1; i < max - 1; i++) picked.push(yearLabels[Math.round(i * step)]);
    picked.push(yearLabels[yearLabels.length - 1]);
    return [...new Map(picked.map((l) => [l.id, l])).values()];
  });
</script>

<div class="timeline ui">
  <div class="controls">
    <button
      class="btn btn-quiet icon"
      onclick={() => engine.stepBack()}
      title={t('tl.prev')}
      aria-label={t('tl.prev')}
      disabled={engine.position <= 0}
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"
        ><path d="M5 3v14M16 3L7 10l9 7z" fill="currentColor" /></svg
      >
    </button>
    <button
      class="btn icon play"
      onclick={() => engine.toggle()}
      title={engine.playing ? t('tl.pause') : t('tl.play')}
      aria-label={engine.playing ? t('tl.pause') : t('tl.play')}
      disabled={engine.versions.length < 2}
    >
      {#if engine.playing}
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"
          ><path d="M5 3h4v14H5zM12 3h4v14h-4z" fill="currentColor" /></svg
        >
      {:else}
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"
          ><path d="M6 3l11 7-11 7z" fill="currentColor" /></svg
        >
      {/if}
    </button>
    <button
      class="btn btn-quiet icon"
      onclick={() => engine.stepForward()}
      title={t('tl.next')}
      aria-label={t('tl.next')}
      disabled={engine.position >= engine.maxPosition}
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"
        ><path d="M15 3v14M4 3l9 7-9 7z" fill="currentColor" /></svg
      >
    </button>
    <button class="btn btn-quiet speed" onclick={() => engine.cycleSpeed()} title={t('tl.speed_title')}>
      {engine.speed}×
    </button>
  </div>

<!-- svelte-ignore a11y_no_static_element_interactions — pointer scrubbing only;
     the keyboard/screen-reader control is the playhead slider inside. -->
  <div
    class="track"
    bind:this={trackEl}
    bind:clientWidth={trackWidth}
    style="height: {trackHeight}px"
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={onPointerUp}
  >
    <!-- Git-graph overlay: the svg itself never eats pointer events; only
         the lane hit strokes re-enable them (pointer-events: stroke). -->
    <svg class="graph" width={Math.max(0, trackWidth)} height={trackHeight}>
      <defs>
        <clipPath id="{uid}-done">
          <rect x="0" y="0" width={Math.max(0, xOf(engine.position))} height={trackHeight} />
        </clipPath>
      </defs>

      <line
        class="rail-line"
        class:hovered={branchName !== 'main' && hoveredLane === 'main'}
        x1={railX.x1}
        y1={railY}
        x2={railX.x2}
        y2={railY}
      />

      {#each lanes.lanes as lane (lane.name)}
        {#if lane.name !== branchName}
          <path
            class="lane-line"
            class:hovered={hoveredLane === lane.name}
            d={lanePathD(lane)}
          />
        {/if}
      {/each}

      <path class="sel-path ahead" d={selectedPathD} />
      <path class="sel-path done" d={selectedPathD} clip-path="url(#{uid}-done)" />

      <!-- Main-rail hit path: when a branch is selected the whole trunk is
           clickable to return to the mainline. Rendered BEFORE the lane hits
           so lane curves win where they cross the rail. -->
      {#if branchName !== 'main'}
        <path
          class="lane-hit"
          d="M {railX.x1} {railY} L {railX.x2} {railY}"
          role="button"
          tabindex="0"
          aria-label={t('tl.main_line_aria')}
          onpointerdown={(e) => e.stopPropagation()}
          onpointerenter={() => (hoveredLane = 'main')}
          onpointerleave={() => (hoveredLane = null)}
          onclick={(e) => {
            e.stopPropagation();
            selectMain();
          }}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              selectMain();
            }
          }}
        />
      {/if}

      {#each lanes.lanes as lane (lane.name)}
        {#if lane.name !== branchName}
          <path
            class="lane-hit"
            d={lanePathD(lane)}
            role="button"
            tabindex="0"
            aria-label={t('tl.lane_line_aria', { name: lane.name })}
            onpointerdown={(e) => e.stopPropagation()}
            onpointerenter={() => (hoveredLane = lane.name)}
            onpointerleave={() => (hoveredLane = null)}
            onclick={(e) => {
              e.stopPropagation();
              selectLane(lane.name, lane.versions[0].id);
            }}
            onkeydown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectLane(lane.name, lane.versions[0].id);
              }
            }}
          />
        {/if}
      {/each}
    </svg>

    {#each engine.versions as version, i (version.id)}
      <button
        class="dot"
        class:passed={engine.position >= i}
        class:endorsed={hasActiveEndorsement(version)}
        style="left: {xOf(i)}px; top: {yOfPathIndex(i)}px"
        title={t('tl.dot_title', { name: version.canonical_form, date: formatDate(version.created_at) })}
        aria-label={t('tl.dot_aria', { n: i + 1, date: formatDate(version.created_at) })}
        onclick={(e) => {
          e.stopPropagation();
          engine.pause();
          engine.seek(i);
        }}
        onpointerdown={(e) => e.stopPropagation()}
      ></button>
    {/each}

    {#each offPathDots as dot (dot.version.id)}
      <button
        class="dot lane-dot"
        class:hovered={hoveredLane === dot.laneName}
        class:endorsed={hasActiveEndorsement(dot.version)}
        style="left: {xOfFrac(dot.frac)}px; top: {dot.y}px"
        title={dot.laneName === 'main'
          ? t('tl.lane_dot_main_aria', { date: formatDate(dot.version.created_at) })
          : t('tl.lane_dot_aria', { name: dot.laneName, date: formatDate(dot.version.created_at) })}
        aria-label={dot.laneName === 'main'
          ? t('tl.lane_dot_main_aria', { date: formatDate(dot.version.created_at) })
          : t('tl.lane_dot_aria', { name: dot.laneName, date: formatDate(dot.version.created_at) })}
        onpointerenter={() => (hoveredLane = dot.laneName)}
        onpointerleave={() => (hoveredLane = null)}
        onclick={(e) => {
          e.stopPropagation();
          selectLane(dot.laneName, dot.version.id);
        }}
        onpointerdown={(e) => e.stopPropagation()}
      ></button>
    {/each}

    <div
      class="playhead"
      style="left: {xOf(engine.position)}px"
      role="slider"
      tabindex="0"
      aria-label={t('tl.slider_aria')}
      aria-valuemin={0}
      aria-valuemax={engine.maxPosition}
      aria-valuenow={Math.round(engine.position * 100) / 100}
      aria-valuetext={valueText}
      aria-keyshortcuts="ArrowLeft ArrowRight Shift+ArrowLeft Shift+ArrowRight ArrowUp ArrowDown Home End Space Enter"
      onkeydown={onKeydown}
    >
      <div class="playhead-line"></div>
      <div class="playhead-knob"></div>
    </div>

    {#each visibleYearLabels as label (label.id)}
      <span class="year mono" style="left: {xOfFrac(label.frac)}px">{label.year}</span>
    {/each}
  </div>
</div>

<style>
  .timeline {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
  }

  .controls {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    flex-shrink: 0;
  }

  /* Mobile: controls above a full-width track — dots need every pixel.
     .timeline-prefixed selectors outrank the later base rules in the cascade. */
  @media (max-width: 620px) {
    .timeline {
      flex-wrap: wrap;
      gap: var(--space-2);
    }

    .timeline .controls {
      order: 1;
      margin: 0 auto;
    }

    .timeline .track {
      order: 2;
      flex: 1 1 100%;
    }
  }

  .icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    padding: 0;
    border-radius: var(--radius-round);
  }

  .play {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
    width: 44px;
    height: 44px;
  }

  .play:hover:not(:disabled) {
    background: color-mix(in srgb, var(--accent) 85%, var(--ink));
  }

  .icon:disabled,
  .play:disabled {
    opacity: 0.35;
    cursor: default;
  }

  .speed {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 0.4em 0.6em;
  }

  .track {
    position: relative;
    flex: 1;
    cursor: pointer;
    touch-action: none;
  }

  .graph {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: visible;
  }

  .rail-line {
    stroke: var(--line);
    stroke-width: 2;
    transition: stroke 0.2s;
  }

  /* Hover preview for the main-rail hit path (return to the trunk). */
  .rail-line.hovered {
    stroke: var(--ink-3);
  }

  .lane-line {
    fill: none;
    stroke: var(--ink-3);
    stroke-width: 1.5;
    stroke-linecap: round;
    opacity: 0.45;
  }

  .lane-line.hovered {
    opacity: 0.85;
  }

  .sel-path {
    fill: none;
    stroke-width: 3;
    stroke-linecap: round;
  }

  .sel-path.ahead {
    stroke: color-mix(in srgb, var(--accent) 30%, transparent);
  }

  .sel-path.done {
    stroke: var(--accent);
  }

  .lane-hit {
    fill: none;
    stroke: transparent;
    stroke-width: 12;
    pointer-events: stroke;
    cursor: pointer;
  }

  .lane-hit:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: 2px;
  }

  .dot {
    position: absolute;
    width: 12px;
    height: 12px;
    padding: 0;
    transform: translate(-50%, -50%);
    border-radius: var(--radius-round);
    border: 2px solid var(--ink-3);
    background: var(--bg-raised);
    cursor: pointer;
    transition: border-color 0.2s, background-color 0.2s, opacity 0.2s, transform 0.15s;
  }

  /* ≥24px touch target even for the small lane dots (mobile!). */
  .dot::before {
    content: '';
    position: absolute;
    inset: -6px;
    border-radius: var(--radius-round);
  }

  .dot:hover {
    transform: translate(-50%, -50%) scale(1.35);
  }

  .dot.passed {
    border-color: var(--accent);
    background: var(--accent);
  }

  /* Endorsed = gold border + a small centered ★ INSIDE the dot (not a halo —
     ui-guardrails §15 icon-state rule: filled + semantic color). */
  .dot.endorsed {
    border-color: var(--endorsed);
  }

  .dot.endorsed::after {
    content: '★'; /* design-guard-exempt: dekorativ pseudo-element-stjärna = fastställd-semantiken, ej komponentbar */
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 7px; /* design-guard-exempt: viz micro-label below the type scale by design */
    line-height: 1;
    color: var(--endorsed);
    pointer-events: none;
  }

  .dot.lane-dot.endorsed::after {
    font-size: 5px; /* design-guard-exempt: viz micro-label below the type scale by design */
  }

  .dot.lane-dot {
    width: 8px;
    height: 8px;
    border-width: 1.5px;
    border-color: color-mix(in srgb, var(--ink-3) 65%, transparent);
    background: var(--bg-raised);
    opacity: 0.7;
  }

  .dot.lane-dot::before {
    inset: -8px;
  }

  .dot.lane-dot:hover,
  .dot.lane-dot.hovered {
    border-color: var(--ink-3);
    opacity: 1;
  }

  .playhead {
    position: absolute;
    top: 8px;
    bottom: 18px;
    transform: translateX(-50%);
    pointer-events: none;
  }

  .playhead:focus-visible {
    outline: none;
  }

  .playhead:focus-visible .playhead-knob {
    outline: 2px solid var(--focus);
    outline-offset: 3px;
  }

  .playhead-line {
    position: absolute;
    left: 50%;
    top: 6px;
    bottom: 0;
    width: 2px;
    transform: translateX(-50%);
    background: var(--ink);
    opacity: 0.7;
  }

  .playhead-knob {
    position: absolute;
    left: 50%;
    top: 0;
    width: 14px;
    height: 14px;
    transform: translateX(-50%);
    border-radius: var(--radius-round);
    background: var(--ink);
    border: 2px solid var(--bg-raised);
    box-shadow: var(--shadow-sm);
  }

  .year {
    position: absolute;
    bottom: 0;
    transform: translateX(-50%);
    color: var(--ink-3);
  }
</style>
