/** Realtime collaborative draft session (TipTap + Yjs against
 * server/app/realtime.py rooms).
 *
 * One session per open edit panel. The shared Y.Doc holds:
 *   - XmlFragment 'definition' — the TipTap document (bound by the
 *     Collaboration extension in DefinitionEditor)
 *   - Y.Map 'fields' — canonical_form: string, note: string,
 *     tags: Y.Array<string>, base_version_id: string
 *
 * Rooms are ephemeral relays: nothing persists server-side, so SEEDING is a
 * client duty. Only the FIRST peer seeds — after the provider's initial
 * sync, an empty fields map means the room is fresh: the fields are then
 * populated in one transact, and `seedMarkdown` flips non-null so the bound
 * editor seeds the fragment (the fragment must NOT be set via the editor
 * `content` option when collab is on). Late joiners adopt room state.
 *
 * Close codes 4403/4404 (accept-then-close, see realtime.py) map to status
 * 'denied' with the server reason; any other loss maps to 'offline'. In both
 * cases the provider stops reconnecting — the edit panel falls back to solo
 * local editing.
 *
 * BROWSER-ONLY: call createCollabSession from $effect/onMount. SSR never
 * runs effects, and this module keeps no window access at module scope. */
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { currentUser } from '$lib/user.svelte';
import { t } from '$lib/i18n.svelte';
import { collabParams, collabRoom, collabServerUrl, peerColor, shouldSeed } from './helpers';

export type CollabStatus = 'connecting' | 'live' | 'denied' | 'offline';

export type CollabFieldKey = 'canonical_form' | 'note' | 'base_version_id';

export interface CollabPeer {
  clientId: number;
  name: string;
  color: string;
  isSelf: boolean;
}

export interface CollabSeed {
  canonical_form: string;
  /** Fragment seed — unused if the room already has content. */
  definition_md: string;
  tags: string[];
  note: string;
  base_version_id: string;
}

/** The slice DefinitionEditor needs to bind TipTap to the shared doc. */
export interface EditorCollab {
  readonly fragment: Y.XmlFragment;
  readonly provider: WebsocketProvider;
  readonly user: { name: string; color: string };
  /** Reactive: markdown to seed into the (empty) fragment — first peer only. */
  readonly seedMarkdown: string | null;
  confirmSeed(): void;
}

export interface CollabSession extends EditorCollab {
  readonly peers: CollabPeer[];
  readonly status: CollabStatus;
  /** Server close reason when status === 'denied'. */
  readonly deniedReason: string | null;
  getField(key: CollabFieldKey): string | undefined;
  getTags(): string[] | undefined;
  setField(key: CollabFieldKey, value: string): void;
  /** Wholesale replace — concurrent tag edits resolve last-writer-wins. */
  setTags(tags: string[]): void;
  /** Deep-observe the fields map; returns the unsubscriber. */
  observeFields(callback: () => void): () => void;
  destroy(): void;
}

export function createCollabSession(options: {
  conceptId: string;
  branch: string;
  seed: CollabSeed;
}): CollabSession {
  const { conceptId, branch, seed } = options;

  const doc = new Y.Doc();
  const fragment = doc.getXmlFragment('definition');
  const fields = doc.getMap<string | Y.Array<string>>('fields');

  const name = currentUser.display_name || currentUser.handle || t('rt.anonymous');
  const user = { name, color: peerColor(name) };

  const provider = new WebsocketProvider(
    collabServerUrl(window.location),
    collabRoom(conceptId, branch),
    doc,
    { params: collabParams(currentUser) }
  );

  let status = $state<CollabStatus>('connecting');
  let deniedReason = $state<string | null>(null);
  let peers = $state<CollabPeer[]>([]);
  let seedMarkdown = $state<string | null>(null);

  let destroyed = false;
  let seedChecked = false;

  // Presence (awareness user states are relayed by the y-protocol itself).
  provider.awareness.setLocalStateField('user', user);
  const rebuildPeers = (): void => {
    if (destroyed) return;
    const self = provider.awareness.clientID;
    peers = [...provider.awareness.getStates().entries()]
      .map(([clientId, state]) => {
        const u = (state as { user?: { name?: string; color?: string } }).user;
        return {
          clientId,
          name: u?.name || t('rt.anonymous'),
          color: u?.color || peerColor(u?.name || ''),
          isSelf: clientId === self
        };
      })
      .sort((a, b) => (a.isSelf ? -1 : b.isSelf ? 1 : a.name.localeCompare(b.name, 'sv')));
  };
  provider.awareness.on('change', rebuildPeers);
  rebuildPeers();

  provider.on('sync', (synced: boolean) => {
    if (destroyed || !synced) return;
    status = 'live';
    if (seedChecked) return;
    seedChecked = true;
    if (!shouldSeed(fields)) return;
    // First peer: populate the fields map atomically; the fragment is seeded
    // by the bound editor (it owns the markdown → ProseMirror → Yjs path).
    doc.transact(() => {
      fields.set('canonical_form', seed.canonical_form);
      fields.set('note', seed.note);
      fields.set('base_version_id', seed.base_version_id);
      const arr = new Y.Array<string>();
      arr.push([...seed.tags]);
      fields.set('tags', arr);
    });
    seedMarkdown = seed.definition_md;
  });

  // Denied/offline are terminal: stop the auto-reconnect (shouldConnect gates
  // y-websocket's backoff timer) and let the edit panel fall back to solo.
  // NOTE: provider.disconnect() must not be called from inside these handlers
  // — the emit happens while provider.ws is still set, so disconnect() would
  // re-emit 'connection-close' with a null event and clobber 'denied'.
  provider.on('connection-close', (event: CloseEvent | null) => {
    if (destroyed || status === 'denied' || status === 'offline') return;
    provider.shouldConnect = false;
    if (event && (event.code === 4403 || event.code === 4404)) {
      status = 'denied';
      deniedReason = event.reason || null;
    } else {
      status = 'offline';
    }
  });

  provider.on('connection-error', () => {
    if (destroyed || status === 'denied' || status === 'offline') return;
    provider.shouldConnect = false;
    status = 'offline';
  });

  return {
    fragment,
    provider,
    user,
    get seedMarkdown() {
      return seedMarkdown;
    },
    confirmSeed() {
      seedMarkdown = null;
    },
    get peers() {
      return peers;
    },
    get status() {
      return status;
    },
    get deniedReason() {
      return deniedReason;
    },
    getField(key) {
      const value = fields.get(key);
      return typeof value === 'string' ? value : undefined;
    },
    getTags() {
      const value = fields.get('tags');
      return value instanceof Y.Array ? (value.toArray() as string[]) : undefined;
    },
    setField(key, value) {
      doc.transact(() => {
        fields.set(key, value);
      });
    },
    setTags(tags) {
      doc.transact(() => {
        const arr = new Y.Array<string>();
        arr.push([...tags]);
        fields.set('tags', arr);
      });
    },
    observeFields(callback) {
      const handler = (): void => callback();
      fields.observeDeep(handler);
      return () => fields.unobserveDeep(handler);
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      provider.awareness.off('change', rebuildPeers);
      provider.destroy();
      doc.destroy();
    }
  };
}
