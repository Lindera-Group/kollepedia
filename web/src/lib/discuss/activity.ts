/** Pure helpers for the activity feed (Iteration 4 — watching & activity). */

import type { ActivityItem } from '$lib/api';
import type { IconName } from '$lib/icons/icons';

export interface DayGroup<T> {
  /** ISO calendar day (yyyy-mm-dd), taken from the item's `at` timestamp. */
  day: string;
  items: T[];
}

/** Groups a chronologically ordered feed into consecutive calendar-day
 * buckets, preserving the input order (the API returns newest first). */
export function groupByDay<T extends { at: string }>(items: T[]): DayGroup<T>[] {
  const groups: DayGroup<T>[] = [];
  for (const item of items) {
    const day = item.at.slice(0, 10);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.items.push(item);
    else groups.push({ day, items: [item] });
  }
  return groups;
}

/** Icon-library glyph per activity kind (ui-guardrails §14: one glyph per
 * concept everywhere — never emoji). Unknown kinds get the neutral pulse. */
const ICON_NAMES: Record<ActivityItem['kind'], IconName> = {
  version: 'edit',
  endorsement: 'star',
  comment: 'talk',
  proposal: 'proposal',
  proposal_merged: 'merge',
  proposal_rejected: 'proposal',
  proposal_withdrawn: 'proposal',
  branch: 'branch',
  merge: 'merge'
};

export function activityIconName(kind: string): IconName {
  return ICON_NAMES[kind as ActivityItem['kind']] ?? 'pulse';
}

/** Kinds whose icon renders filled + colored (endorsed gold). */
export function activityIconFilled(kind: string): boolean {
  return kind === 'endorsement';
}
