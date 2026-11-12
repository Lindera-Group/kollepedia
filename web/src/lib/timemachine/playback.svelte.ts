/** The playback engine: history as video.
 *
 * `position` is a float over [0, versions.length - 1]: integer = at rest on
 * that version, fraction = inside the transition to the next one. Each frame
 * writes four eased phase variables (--p1 marking, --p2 typing, --p3 collapse,
 * --p4 settle) onto the stage element; all word/char styling is CSS calc()
 * over those, so scrubbing costs one style write, not a re-render.
 */

import type { VersionOut } from '$lib/api';
import type { Transition } from './script';

const HOLD_END = 0.04;
const SETTLE_START = 0.94;

function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function phaseProgress(u: number, from: number, to: number): number {
  if (u <= from) return 0;
  if (u >= to) return 1;
  return (u - from) / (to - from);
}

function countPassed(sortedThresholds: number[], pm: number): number {
  let count = 0;
  for (const threshold of sortedThresholds) {
    if (threshold <= pm) count++;
    else break;
  }
  return count;
}

export interface Phases {
  /** Master progress: every changed word's windows live on this axis. */
  pm: number;
  /** Settle: green washes dissolve, the new version comes to rest. */
  p4: number;
}

export function phasesAt(u: number): Phases {
  return {
    pm: phaseProgress(u, HOLD_END, SETTLE_START),
    p4: easeInOut(phaseProgress(u, SETTLE_START, 1))
  };
}

export class Playback {
  versions: VersionOut[];
  transitions: Transition[];

  position = $state(0);
  playing = $state(false);
  speed = $state(1);

  /** Coarse threshold states rendered by Svelte (breaks can't be CSS-driven). */
  typedBreaks = $state(0);
  goneDelBreaks = $state(0);
  /** Fields swap: show the target version's values past mid-transition. */
  swapped = $state(false);

  private el: HTMLElement | null = null;
  private raf = 0;
  private lastT = 0;

  constructor(versions: VersionOut[], transitions: Transition[]) {
    this.versions = versions;
    this.transitions = transitions;
  }

  get maxPosition(): number {
    return Math.max(0, this.versions.length - 1);
  }

  /** Which transition the stage is rendering (last one held at u=1 at the end). */
  get displayIndex(): number {
    if (this.transitions.length === 0) return 0;
    return Math.min(Math.floor(this.position), this.transitions.length - 1);
  }

  get u(): number {
    if (this.transitions.length === 0) return 0;
    return Math.min(1, this.position - this.displayIndex);
  }

  get atRest(): boolean {
    return Math.abs(this.position - Math.round(this.position)) < 1e-3;
  }

  /** Version index shown at rest, or the one we are heading toward mid-flight. */
  get focusIndex(): number {
    return this.atRest ? Math.round(this.position) : Math.ceil(this.position);
  }

  attach(el: HTMLElement): void {
    this.el = el;
    this.applyFrame();
  }

  destroy(): void {
    cancelAnimationFrame(this.raf);
    this.playing = false;
  }

  play(): void {
    if (this.versions.length < 2) return;
    if (this.position >= this.maxPosition) this.position = 0;
    this.playing = true;
    this.lastT = performance.now();
    cancelAnimationFrame(this.raf);
    this.raf = requestAnimationFrame(this.loop);
  }

  pause(): void {
    this.playing = false;
    cancelAnimationFrame(this.raf);
  }

  toggle(): void {
    if (this.playing) this.pause();
    else this.play();
  }

  seek(position: number): void {
    this.position = Math.min(this.maxPosition, Math.max(0, position));
    this.applyFrame();
  }

  stepForward(): void {
    this.pause();
    this.seek(this.atRest ? Math.round(this.position) + 1 : Math.ceil(this.position));
  }

  stepBack(): void {
    this.pause();
    this.seek(this.atRest ? Math.round(this.position) - 1 : Math.floor(this.position));
  }

  cycleSpeed(): void {
    this.speed = this.speed >= 2 ? 0.5 : this.speed + 0.5;
  }

  private loop = (t: number): void => {
    if (!this.playing) return;
    const dt = Math.min(0.1, (t - this.lastT) / 1000);
    this.lastT = t;
    const duration = this.transitions[this.displayIndex]?.duration ?? 1;
    this.position = Math.min(this.maxPosition, this.position + (dt * this.speed) / duration);
    this.applyFrame();
    if (this.position >= this.maxPosition) {
      this.playing = false;
      return;
    }
    this.raf = requestAnimationFrame(this.loop);
  };

  applyFrame(): void {
    if (!this.el) return;
    const { pm, p4 } = phasesAt(this.u);
    const style = this.el.style;
    style.setProperty('--pm', pm.toFixed(4));
    style.setProperty('--p4', p4.toFixed(4));

    const transition = this.transitions[this.displayIndex];
    if (transition) {
      const typed = countPassed(transition.insBreakThresholds, pm);
      if (typed !== this.typedBreaks) this.typedBreaks = typed;
      const gone = countPassed(transition.delBreakThresholds, pm);
      if (gone !== this.goneDelBreaks) this.goneDelBreaks = gone;
      const swapped = pm >= 0.5;
      if (swapped !== this.swapped) this.swapped = swapped;
    }
  }
}
