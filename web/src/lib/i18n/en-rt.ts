import type { RtKey } from './sv-rt';

/** Realtime co-editing keys (English) — typed against the sv-rt key union so
 * a missing or extra key is a compile-time error. */
export const enRt: Record<RtKey, string> = {
  'rt.live': 'Live',
  'rt.connecting': 'Connecting …',
  'rt.denied': 'Denied: {reason}',
  'rt.denied_generic': 'Denied',
  'rt.offline': 'Offline — you are editing alone',
  'rt.peers_aria': 'Real-time co-editors',
  'rt.you': 'you',
  'rt.anonymous': 'Anonymous',
  'rt.saved': 'Version {n} saved',
  'rt.remote_saved': 'A co-editor saved a new version — you are now editing on top of it.',
  'rt.textarea_disabled_hint': 'Text mode is read-only during co-editing — edit in the visual mode.'
};
