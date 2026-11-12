/** Builds the choreography for one version transition.
 *
 * Every changed word gets its own time window over a single master progress
 * variable (--pm ∈ 0..1): deleted words get a mark window (red wash fades in)
 * and a collapse window (curtain closes); inserted words get a typing window.
 * All numbers are precomputed here; per-frame work is only two CSS-variable
 * writes (--pm, --p4) on the stage (see playback + component CSS).
 *
 * Two window layouts:
 * - 'sequential' (default): edits play out hunk by hunk along the text, the
 *   way an editor would work start-to-finish — mark the deletion, type the
 *   replacement, dissolve the red, move on.
 * - 'global': the original choreography — all deletions mark first, then all
 *   insertions type, then all red collapses at once.
 */

import type { VersionOut } from '$lib/api';
import { diffTokens, tokenize, type DiffOp } from './diff';
import { stripMarkdown } from '$lib/text';

export type AnimationOrder = 'sequential' | 'global';

/** Flip to 'global' to restore the original all-at-once choreography. */
export const DEFAULT_ORDER: AnimationOrder = 'sequential';

const HOLD_END = 0.04;
const SETTLE_START = 0.94;
const EPS = 1e-4;

export interface WordSpan {
  type: 'eq' | 'del' | 'ins';
  kind: 'word' | 'break';
  text: string;
  /** Token index in version A / B token arrays (for blame + ink lookups). */
  aIdx: number | null;
  bIdx: number | null;
  /** ins words: typing window over --pm. */
  a?: number;
  span?: number;
  chars?: string[];
  /** ins breaks: ordinal among inserted breaks (visibility threshold). */
  breakOrdinal?: number;
  /** del words: mark window (ma/ms) and collapse window (ca/cs) over --pm. */
  ma?: number;
  ms?: number;
  ca?: number;
  cs?: number;
  /** del breaks: ordinal among deleted breaks (hidden once collapsed). */
  delBreakOrdinal?: number;
}

export interface PillChange {
  label: string;
  state: 'kept' | 'added' | 'removed';
}

export interface FieldChange {
  field: 'status' | 'language';
  from: string;
  to: string;
}

export interface Transition {
  order: AnimationOrder;
  title: WordSpan[];
  def: WordSpan[];
  pills: PillChange[];
  fields: FieldChange[];
  insChars: number;
  delChars: number;
  /** Seconds at speed 1. */
  duration: number;
  /** True when the raw markdown changed but the animated prose did not —
   * bold/italic/links only. The stage shows a discreet marker instead of
   * a false-empty diff. */
  formattingOnly: boolean;
  /** --pm thresholds at which inserted/deleted breaks toggle (both sorted). */
  insBreakThresholds: number[];
  delBreakThresholds: number[];
}

function opsToSpans(ops: DiffOp[]): WordSpan[] {
  const spans: WordSpan[] = [];
  let aIdx = 0;
  let bIdx = 0;
  for (const op of ops) {
    for (const token of op.tokens) {
      const span: WordSpan = {
        type: op.type,
        kind: token.kind,
        text: token.text,
        aIdx: op.type === 'ins' ? null : aIdx,
        bIdx: op.type === 'del' ? null : bIdx
      };
      if (op.type === 'ins' && token.kind === 'word') span.chars = [...token.text];
      spans.push(span);
      if (op.type !== 'ins') aIdx++;
      if (op.type !== 'del') bIdx++;
    }
  }
  return spans;
}

interface Hunk {
  del: WordSpan[];
  ins: WordSpan[];
  delChars: number;
  insChars: number;
}

function spanChars(span: WordSpan): number {
  return span.kind === 'break' ? 1 : span.text.length;
}

/** Group consecutive del/ins spans into edit hunks, in reading order. */
function collectHunks(spans: WordSpan[]): Hunk[] {
  const hunks: Hunk[] = [];
  let current: Hunk | null = null;
  for (const span of spans) {
    if (span.type === 'eq') {
      current = null;
      continue;
    }
    if (!current) {
      current = { del: [], ins: [], delChars: 0, insChars: 0 };
      hunks.push(current);
    }
    if (span.type === 'del') {
      current.del.push(span);
      current.delChars += spanChars(span);
    } else {
      current.ins.push(span);
      current.insChars += spanChars(span);
    }
  }
  return hunks;
}

interface LayoutResult {
  insBreakThresholds: number[];
  delBreakThresholds: number[];
}

/** Distribute typing windows for a hunk's inserted spans across [start, start+width]. */
function layoutInsWindows(
  hunk: Hunk,
  start: number,
  width: number,
  result: LayoutResult
): void {
  let charCursor = 0;
  for (const span of hunk.ins) {
    const length = spanChars(span);
    const at = start + (hunk.insChars > 0 ? (charCursor / hunk.insChars) * width : 0);
    if (span.kind === 'break') {
      span.a = at;
      span.breakOrdinal = result.insBreakThresholds.length;
      result.insBreakThresholds.push(at);
    } else {
      span.a = at;
      span.span = Math.max(hunk.insChars > 0 ? (length / hunk.insChars) * width : width, EPS);
    }
    charCursor += length;
  }
}

function layoutDelWindows(
  hunk: Hunk,
  ma: number,
  ms: number,
  ca: number,
  cs: number,
  result: LayoutResult
): void {
  for (const span of hunk.del) {
    span.ma = ma;
    span.ms = Math.max(ms, EPS);
    span.ca = ca;
    span.cs = Math.max(cs, EPS);
    if (span.kind === 'break') {
      const threshold = ca + cs * 0.5;
      span.delBreakOrdinal = result.delBreakThresholds.length;
      result.delBreakThresholds.push(threshold);
    }
  }
}

/** Sequential: hunks play in reading order — mark, type, dissolve, next. */
function layoutSequential(hunks: Hunk[], result: LayoutResult): void {
  const costs = hunks.map((hunk) => ({
    mark: hunk.delChars > 0 ? 0.55 + Math.min(hunk.delChars / 120, 1.2) : 0,
    type: hunk.insChars > 0 ? Math.max(hunk.insChars / 30, 0.3) : 0,
    collapse: hunk.delChars > 0 ? 0.45 + Math.min(hunk.delChars / 200, 0.8) : 0
  }));
  const total = costs.reduce((sum, c) => sum + c.mark + c.type + c.collapse, 0);
  if (total <= 0) return;
  const scale = (SETTLE_START - HOLD_END) / total;
  let cursor = HOLD_END;
  hunks.forEach((hunk, i) => {
    const mark = costs[i].mark * scale;
    const type = costs[i].type * scale;
    const collapse = costs[i].collapse * scale;
    layoutDelWindows(hunk, cursor, mark, cursor + mark + type, collapse, result);
    layoutInsWindows(hunk, cursor + mark, type, result);
    cursor += mark + type + collapse;
  });
}

/** Global: the original beats — all mark, then all type, then all collapse. */
function layoutGlobal(hunks: Hunk[], result: LayoutResult): void {
  const totalIns = hunks.reduce((sum, h) => sum + h.insChars, 0);
  const TYPE_START = 0.26;
  const TYPE_WIDTH = 0.48;
  let charCursor = 0;
  for (const hunk of hunks) {
    layoutDelWindows(hunk, 0.06, 0.18, 0.78, 0.12, result);
    const start = TYPE_START + (totalIns > 0 ? (charCursor / totalIns) * TYPE_WIDTH : 0);
    const width = totalIns > 0 ? (hunk.insChars / totalIns) * TYPE_WIDTH : TYPE_WIDTH;
    layoutInsWindows(hunk, start, width, result);
    charCursor += hunk.insChars;
  }
}

export function buildTransition(
  a: VersionOut,
  b: VersionOut,
  order: AnimationOrder = DEFAULT_ORDER
): Transition {
  const title = opsToSpans(diffTokens(tokenize(a.canonical_form), tokenize(b.canonical_form)));
  const def = opsToSpans(
    diffTokens(tokenize(stripMarkdown(a.definition_md)), tokenize(stripMarkdown(b.definition_md)))
  );

  // Title hunks and definition hunks stay separate so the title always
  // resolves before the definition starts (reading order).
  const hunks = [...collectHunks(title), ...collectHunks(def)];
  const result: LayoutResult = { insBreakThresholds: [], delBreakThresholds: [] };
  if (order === 'sequential') layoutSequential(hunks, result);
  else layoutGlobal(hunks, result);

  const insChars = hunks.reduce((sum, h) => sum + h.insChars, 0);
  const delChars = hunks.reduce((sum, h) => sum + h.delChars, 0);

  const aTags = new Set(a.tags);
  const bTags = new Set(b.tags);
  const pills: PillChange[] = [];
  for (const tag of a.tags) pills.push({ label: tag, state: bTags.has(tag) ? 'kept' : 'removed' });
  for (const tag of b.tags) if (!aTags.has(tag)) pills.push({ label: tag, state: 'added' });

  const fields: FieldChange[] = [];
  if (a.status !== b.status) fields.push({ field: 'status', from: a.status, to: b.status });
  if (a.language !== b.language) fields.push({ field: 'language', from: a.language, to: b.language });

  const changed = insChars > 0 || delChars > 0 || pills.some((p) => p.state !== 'kept');
  const duration = changed
    ? Math.min(9, Math.max(2.4, 1.8 + insChars / 45 + delChars / 110 + hunks.length * 0.2))
    : 1.4;
  // Independent of field changes (a status bump can accompany it) — the
  // marker means "the markdown changed but the animated prose did not".
  const formattingOnly =
    !changed && (a.definition_md !== b.definition_md || a.canonical_form !== b.canonical_form);

  return {
    order,
    title,
    def,
    pills,
    fields,
    insChars,
    delChars,
    duration,
    formattingOnly,
    insBreakThresholds: result.insBreakThresholds,
    delBreakThresholds: result.delBreakThresholds
  };
}

/** Spans for a single version at rest (no transition — e.g. a one-version concept). */
export function restSpans(version: VersionOut): { title: WordSpan[]; def: WordSpan[] } {
  const make = (text: string): WordSpan[] =>
    tokenize(text).map((token, i) => ({
      type: 'eq' as const,
      kind: token.kind,
      text: token.text,
      aIdx: i,
      bIdx: i
    }));
  return { title: make(version.canonical_form), def: make(stripMarkdown(version.definition_md)) };
}
