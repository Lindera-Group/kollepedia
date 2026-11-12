<script lang="ts">
  /** Field-wise editing on the version graph (VISION §12 Phase 1).
   * Save = new immutable version via mode 'revise'; a 409 on a stale base
   * offers branch-and-reconcile (VISION §4.5) instead of overwriting.
   *
   * Realtime co-editing: the panel joins the concept's 'main' Yjs room on
   * open (browser-only, in an effect — SSR never runs it). The definition is
   * co-edited through the shared fragment; canonical form, note and tags sync
   * through the shared fields map. On denied/offline the panel falls back
   * seamlessly to solo local editing (session absent). */
  import { untrack } from 'svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { VERSION_STATUSES } from '$lib/search/statuses';
  import { api, ApiError, type ConceptOut, type ProposalOut, type VersionOut } from '$lib/api';
  import { createCollabSession, type CollabSession } from '$lib/collab/session.svelte';
  import { errorMessage } from '$lib/errors';
  import { statusLabel, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import HelpTip from '$lib/help/HelpTip.svelte';
  import DefinitionEditor from '$lib/editor/DefinitionEditor.svelte';
  import ProposalForm from '$lib/proposals/ProposalForm.svelte';
  import TagEditor from './TagEditor.svelte';

  interface Props {
    concept: ConceptOut;
    head: VersionOut;
    oncancel: () => void;
    onsaved: (mode: 'revise' | 'branch', branchName?: string) => void;
  }

  let { concept, head, oncancel, onsaved }: Props = $props();

  const STATUSES = VERSION_STATUSES;

  // The base is deliberately frozen at panel-open time (the parent mounts a
  // fresh panel per edit session) — a concurrent edit must surface as a 409,
  // never as a silent rebase onto a head the user hasn't seen.
  // svelte-ignore state_referenced_locally
  const base = $state.snapshot(head);
  const baseVersionId = base.id;

  let canonicalForm = $state(base.canonical_form);
  let definitionMd = $state(base.definition_md);
  // Legacy 'endorsed' rows can still exist pre-migration — coerce like the server.
  let status = $state(base.status === 'endorsed' ? 'proposed' : base.status);
  let tags = $state([...base.tags]);
  let note = $state('');

  let branchMode = $state(false);
  let conflict = $state(false);
  let branchName = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);
  let noteError = $state<string | null>(null);
  let formError = $state<string | null>(null);

  // Iteration 4: after a successful branch save, offer to submit the branch as
  // a change proposal before handing control back to the parent.
  let savedBranch = $state<string | null>(null);
  let savedNote = $state('');
  let proposal = $state<ProposalOut | null>(null);

  // ── Realtime co-editing (Yjs room concept.<id>.main) ──
  let session = $state.raw<CollabSession | null>(null);
  let fallbackStatus = $state<'denied' | 'offline' | null>(null);
  let fallbackReason = $state<string | null>(null);
  /** A co-editor saved a new version — we now edit against it. */
  let remoteSaved = $state(false);
  /** Set after our own save while peers are present ("Version N sparad"). */
  let savedVersionN = $state<number | null>(null);
  /** Loop guard: our own field pushes must not bounce back via the observer. */
  let applying = false;
  /** The base a save must build on: the room's shared base_version_id (peers
   * may have saved), falling back to the frozen panel base when solo. */
  let lastKnownBase = baseVersionId;
  /** Versions saved through this room while the panel is open (ours+theirs). */
  let roomSaves = 0;

  // Join the room once on mount (untracked — the room identity is frozen with
  // the base); leave it on unmount. Effects never run during SSR, so all
  // Y.Doc/WebSocket work stays browser-only.
  $effect(() => {
    const s = untrack(() =>
      createCollabSession({
        conceptId: concept.id,
        branch: 'main',
        seed: {
          canonical_form: base.canonical_form,
          definition_md: base.definition_md,
          tags: [...base.tags],
          note: '',
          base_version_id: baseVersionId
        }
      })
    );
    const unobserve = s.observeFields(() => {
      if (applying) return;
      const cf = s.getField('canonical_form');
      if (cf !== undefined && cf !== canonicalForm) canonicalForm = cf;
      const n = s.getField('note');
      if (n !== undefined && n !== note) note = n;
      const nextTags = s.getTags();
      if (nextTags && JSON.stringify(nextTags) !== JSON.stringify(tags)) tags = nextTags;
      const bv = s.getField('base_version_id');
      if (bv && bv !== lastKnownBase) {
        // A save landed elsewhere in the room — rebase silently onto it.
        lastKnownBase = bv;
        roomSaves += 1;
        remoteSaved = true;
        savedVersionN = null;
      }
    });
    session = s;
    return () => {
      unobserve();
      s.destroy();
      session = null;
    };
  });

  // Denied/offline → seamless fallback to solo local editing (the $state
  // fields already mirror the latest shared values; the editor remounts from
  // the serialized markdown).
  $effect(() => {
    const s = session;
    if (!s) return;
    if (s.status === 'denied' || s.status === 'offline') {
      fallbackStatus = s.status;
      fallbackReason = s.deniedReason;
      s.destroy();
      session = null;
    }
  });

  const collabConnecting = $derived(session?.status === 'connecting');
  const rtStatus = $derived(session ? session.status : fallbackStatus);
  const rtReason = $derived(session ? session.deniedReason : fallbackReason);
  const rtLabel = $derived.by(() => {
    switch (rtStatus) {
      case 'live':
        return t('rt.live');
      case 'connecting':
        return t('rt.connecting');
      case 'denied':
        return rtReason ? t('rt.denied', { reason: rtReason }) : t('rt.denied_generic');
      case 'offline':
        return t('rt.offline');
      default:
        return '';
    }
  });

  function peerInitial(peerName: string): string {
    return peerName.trim().charAt(0).toUpperCase() || '?';
  }

  /** Local input → shared fields map (one transact per keystroke is fine —
   * Yjs batches map sets efficiently). */
  function pushField(key: 'canonical_form' | 'note' | 'base_version_id', value: string): void {
    const s = session;
    if (!s || s.status !== 'live') return;
    applying = true;
    try {
      s.setField(key, value);
    } finally {
      applying = false;
    }
  }

  function updateCanonical(value: string): void {
    canonicalForm = value;
    pushField('canonical_form', value);
  }

  function updateNote(value: string): void {
    note = value;
    pushField('note', value);
  }

  function updateTags(next: string[]): void {
    tags = next;
    const s = session;
    if (!s || s.status !== 'live') return;
    applying = true;
    try {
      s.setTags(next);
    } finally {
      applying = false;
    }
  }

  /** Our save became the room's new base: hand it to the peers. */
  function registerLocalSave(versionId: string): void {
    lastKnownBase = versionId;
    roomSaves += 1;
    remoteSaved = false;
    pushField('base_version_id', versionId);
  }

  function finishBranch(): void {
    if (savedBranch) onsaved('branch', savedBranch);
  }

  function defaultBranchName(): string {
    const handle = currentUser.handle || 'anonym';
    return `gren-av-${handle.toLowerCase().replace(/\s+/g, '-')}`;
  }

  function openBranchMode(): void {
    branchMode = true;
    if (!branchName.trim()) branchName = defaultBranchName();
  }

  function closeBranchMode(): void {
    branchMode = false;
    conflict = false;
    error = null;
  }

  const asBranch = $derived(branchMode || conflict);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    noteError = null;
    formError = null;

    if (!canonicalForm.trim()) {
      formError = t('edit.error_no_name');
      return;
    }
    if (!note.trim()) {
      noteError = t('edit.error_no_note');
      return;
    }
    if (asBranch && !branchName.trim()) {
      error = t('edit.error_no_branch_name');
      return;
    }

    saving = true;
    try {
      // The room's shared base wins over the frozen panel base — a peer may
      // have saved while we edited. A 409 is still possible (stale room after
      // a save outside it) and keeps flowing into branch-and-reconcile.
      const payload = {
        base_version_id: lastKnownBase,
        canonical_form: canonicalForm.trim(),
        definition_md: definitionMd,
        status,
        tags,
        note: note.trim(),
        language: base.language
      };
      if (asBranch) {
        const name = branchName.trim();
        await api.createVersion(concept.id, { ...payload, mode: 'branch', branch_name: name });
        savedBranch = name;
        savedNote = note.trim();
      } else {
        const created = await api.createVersion(concept.id, { ...payload, mode: 'revise' });
        registerLocalSave(created.id);
        if (session && session.peers.some((p) => !p.isSelf)) {
          // Peers present: keep the shared session open — closing stays
          // manual. The inline notice confirms the save.
          savedVersionN = concept.version_count + roomSaves;
        } else {
          onsaved('revise');
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && !asBranch) {
        conflict = true;
        if (!branchName.trim()) branchName = defaultBranchName();
      } else {
        error = errorMessage(e);
      }
    } finally {
      saving = false;
    }
  }
</script>

{#if savedBranch}
  <div class="edit-panel">
    <p class="followup-msg ui" role="status">
      <Icon name="check" size={14} /> {t('prop.branch_followup', { name: savedBranch })}
    </p>
    {#if proposal}
      <p class="followup-done ui" role="status">
        <Icon name="check" size={14} /> {t('prop.created')} {t('typo.dash')} <a href="/proposals/{proposal.id}">{t('prop.created_link')}</a>
      </p>
      <div class="actions ui">
        <button type="button" class="btn" onclick={finishBranch}>{t('common.close')}</button>
      </div>
    {:else}
      <ProposalForm
        conceptId={concept.id}
        fixedBranch={savedBranch}
        initialTitle={savedNote}
        oncreated={(created) => (proposal = created)}
        oncancel={finishBranch}
        cancelLabel={t('prop.followup_skip')}
      />
    {/if}
  </div>
{:else}
<form class="edit-panel" onsubmit={submit} aria-label={t('edit.aria')}>
  <h2 class="panel-title">{t('edit.title')}</h2>
  {#if rtStatus}
    <div class="presence ui" aria-label={t('rt.peers_aria')}>
      <span class="rt-dot {rtStatus}" aria-hidden="true"></span>
      <span class="rt-label" role="status">{rtLabel}</span>
      {#if session}
        {#each session.peers as peer (peer.clientId)}
          <span
            class="rt-chip"
            style="background-color: {peer.color}"
            title={peer.isSelf ? `${peer.name} (${t('rt.you')})` : peer.name}
          >{peerInitial(peer.name)}</span
          >{#if peer.isSelf}<span class="rt-you">{t('rt.you')}</span>{/if}
        {/each}
      {/if}
    </div>
  {/if}
  <p class="panel-sub ui">
    {t('edit.subtitle')}
    <strong>{currentUser.handle}</strong>.
  </p>

  <div class="field">
    <label class="ui" for="edit-canonical">{t('edit.canonical_label')}</label>
    <input
      id="edit-canonical"
      class="input canonical"
      type="text"
      value={canonicalForm}
      oninput={(event) => updateCanonical(event.currentTarget.value)}
      disabled={saving || collabConnecting}
      required
    />
    {#if formError}<p class="field-error ui" role="alert">{formError}</p>{/if}
  </div>

  <div class="field">
    <label class="ui" for="edit-definition">{t('edit.definition_label')}</label>
    <DefinitionEditor
      inputId="edit-definition"
      value={definitionMd}
      onchange={(md) => (definitionMd = md)}
      disabled={saving || collabConnecting}
      collab={session}
    />
    <p class="field-hint ui">
      {t('edit.markdown_hint')}
    </p>
  </div>

  <div class="row">
    <div class="field grow">
      <label class="ui" for="edit-tags">{t('edit.tags_label')}</label>
      <TagEditor
        {tags}
        onchange={updateTags}
        disabled={saving || collabConnecting}
        inputId="edit-tags"
      />
    </div>

    <div class="field">
      <label class="ui" for="edit-status">{t('common.status')}</label>
      <select id="edit-status" class="input" bind:value={status} disabled={saving}>
        {#each STATUSES as s (s)}
          <option value={s}>{statusLabel(s)}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="field">
    <label class="ui" for="edit-note"
      >{t('edit.note_label')} <span class="req" aria-hidden="true">·&nbsp;{t('edit.note_required')}</span>
      <HelpTip topic="editing-note" /></label
    >
    <textarea
      id="edit-note"
      class="input note"
      rows="3"
      value={note}
      oninput={(event) => updateNote(event.currentTarget.value)}
      disabled={saving || collabConnecting}
      placeholder={t('edit.note_placeholder')}
      aria-describedby={noteError ? 'edit-note-error' : undefined}
    ></textarea>
    {#if noteError}<p class="field-error ui" id="edit-note-error" role="alert">{noteError}</p>{/if}
  </div>

  {#if remoteSaved}
    <p class="rt-notice ui" role="status">{t('rt.remote_saved')}</p>
  {/if}
  {#if savedVersionN !== null}
    <p class="rt-saved ui" role="status"><Icon name="check" size={14} /> {t('rt.saved', { n: savedVersionN })}</p>
  {/if}

  {#if conflict}
    <div class="conflict ui" role="alert">
      <p class="conflict-msg">
        <strong>{t('edit.conflict_title')}</strong> {t('edit.conflict_body')}
      </p>
    </div>
  {/if}

  {#if asBranch}
    <div class="field branch-field">
      <label class="ui" for="edit-branch-name">{t('edit.branch_name_label')}</label>
      <input
        id="edit-branch-name"
        class="input"
        type="text"
        bind:value={branchName}
        disabled={saving}
        autocomplete="off"
        spellcheck="false"
      />
    </div>
  {/if}

  {#if error}
    <p class="error ui" role="alert">{error}</p>
  {/if}

  <div class="actions ui">
    {#if asBranch}
      <button type="submit" class="btn btn-primary" disabled={saving}>
        {saving ? t('edit.creating_branch') : t('edit.create_branch')}
      </button>
      {#if conflict}
        <button type="button" class="btn btn-quiet" disabled={saving} onclick={closeBranchMode}>
          {t('edit.back_to_edit')}
        </button>
      {:else}
        <button type="button" class="btn btn-quiet" disabled={saving} onclick={closeBranchMode}>
          {t('edit.save_on_main')}
        </button>
      {/if}
    {:else}
      <button type="submit" class="btn btn-primary" disabled={saving}>
        {saving ? t('common.saving') : t('edit.save_new_version')}
      </button>
      <button
        type="button"
        class="btn"
        disabled={saving}
        onclick={openBranchMode}
        title={t('edit.create_branch_title')}
      >
        {t('edit.create_branch')}
      </button>
    {/if}
    <button type="button" class="btn btn-quiet" disabled={saving} onclick={oncancel}>{t('common.cancel')}</button>
  </div>
</form>
{/if}

<style>
  .edit-panel {
    /* Fills the tool subview (2026-07-12 width cleanup) — the subview's 70ch
       is the single width authority; nested caps made the form look ragged. */
    max-width: none;
    margin: var(--space-6) 0;
    padding: var(--space-6);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
  }

  .panel-title {
    font-size: var(--text-lg);
    margin-bottom: var(--space-1);
  }

  .panel-sub {
    font-size: var(--text-sm);
    color: var(--ink-3);
    margin-bottom: var(--space-6);
  }

  /* ── Realtime presence row ── */
  .presence {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    font-size: var(--text-xs);
  }

  .rt-dot {
    width: 0.55em;
    height: 0.55em;
    border-radius: var(--radius-round);
    background: var(--ink-3);
    flex: none;
  }

  .rt-dot.live {
    background: var(--ins-strong);
  }

  .rt-dot.denied {
    background: var(--del-strong);
  }

  .rt-label {
    color: var(--ink-3);
    letter-spacing: 0.02em;
  }

  .rt-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.7em;
    height: 1.7em;
    border-radius: var(--radius-round);
    color: var(--on-accent);
    font-weight: 600;
    font-size: var(--text-xs);
    line-height: 1;
    user-select: none;
  }

  .rt-you {
    color: var(--ink-3);
    margin-left: calc(-1 * var(--space-1));
  }

  .rt-notice {
    margin-bottom: var(--space-4);
    padding: var(--space-2) var(--space-3);
    border-left: 2px solid var(--accent);
    background: var(--accent-soft);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .rt-saved {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    margin-bottom: var(--space-4);
    font-size: var(--text-sm);
    color: var(--ins-strong);
  }

  .field {
    margin-bottom: var(--space-4);
  }

  .row {
    display: flex;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .grow {
    flex: 1;
    min-width: 240px;
  }

  label {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    margin-bottom: var(--space-1);
  }

  .req {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  input[type='text'],
  textarea,
  select {
    width: 100%;
  }

  .canonical {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    font-weight: 560;
    letter-spacing: -0.01em;
  }

  .note {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    line-height: 1.5;
    resize: vertical;
  }

  select {
    width: auto;
    min-width: 160px;
  }

  .field-hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: var(--space-1) 0 0;
  }

  .field-error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: var(--space-1) 0 0;
  }

  .conflict {
    margin-bottom: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
  }

  .conflict-msg {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .branch-field input {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin-bottom: var(--space-4);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .followup-msg {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin-bottom: var(--space-4);
  }

  .followup-done {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin-bottom: var(--space-4);
  }
</style>
