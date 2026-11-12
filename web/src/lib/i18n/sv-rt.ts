/** Realtime co-editing keys (Swedish) — presence row, connection status and
 * shared-save notices in the edit panel. Spread into the sv dict in ./sv.ts
 * next to the collab/extra spreads; en-rt.ts is typed against this union. */
export const svRt = {
  'rt.live': 'Live',
  'rt.connecting': 'Ansluter …',
  'rt.denied': 'Nekad: {reason}',
  'rt.denied_generic': 'Nekad',
  'rt.offline': 'Offline – du redigerar ensam',
  'rt.peers_aria': 'Medredigerare i realtid',
  'rt.you': 'du',
  'rt.anonymous': 'Anonym',
  'rt.saved': 'Version {n} sparad',
  'rt.remote_saved': 'Ny version sparades av en medredigerare – ni redigerar nu vidare mot den.',
  'rt.textarea_disabled_hint':
    'Textläget är skrivskyddat under samredigering – redigera i det visuella läget.'
} as const;

export type RtKey = keyof typeof svRt;
