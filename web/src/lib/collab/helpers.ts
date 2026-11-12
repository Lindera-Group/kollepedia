/** Pure helpers for the realtime collab session — kept rune-free so they can
 * be unit-tested in a plain node environment (see helpers.test.ts). */

/** Eight peer hues, all ≥ 4.5:1 (WCAG AA) against white text — used for both
 * presence chips and CollaborationCursor carets/labels (white label text). */
export const PEER_PALETTE = [
  '#b3261e', // red
  '#9c4a00', // amber-brown
  '#1b6e53', // green
  '#00666e', // teal
  '#0f4c81', // blue
  '#5746af', // indigo
  '#7b2d8b', // purple
  '#a01a58' // magenta
] as const;

/** Deterministic name → palette colour (djb2 hash). The same handle gets the
 * same hue in every tab and for every peer. */
export function peerColor(name: string): string {
  let hash = 5381;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 33) ^ name.charCodeAt(i);
  }
  return PEER_PALETTE[(hash >>> 0) % PEER_PALETTE.length];
}

/** ws/wss base URL for the collab endpoint, derived from the page location
 * (same host — Vite proxies /ws to the backend in dev). y-websocket appends
 * `/<room>?<params>` itself. */
export function collabServerUrl(loc: { protocol: string; host: string }): string {
  const scheme = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${loc.host}/ws/collab`;
}

/** Room auth query params (realtime.py): a real JWT wins, the dev handle
 * falls back to ?who=, and anonymous sends nothing (open collections). */
export function collabParams(session: {
  token: string | null;
  handle: string;
}): Record<string, string> {
  if (session.token) return { token: session.token };
  const who = session.handle.trim();
  if (who) return { who };
  return {};
}

/** Room name: `concept.<concept_id>.<branch>` (ids are UUIDs — dot-free). */
export function collabRoom(conceptId: string, branch: string): string {
  return `concept.${conceptId}.${branch}`;
}

/** Seeding decision: only the FIRST peer seeds — after provider sync, an
 * empty fields map means nobody has populated the room yet. */
export function shouldSeed(fields: { size: number }): boolean {
  return fields.size === 0;
}
