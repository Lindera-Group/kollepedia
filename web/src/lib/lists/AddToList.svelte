<script lang="ts">
  import { api, ApiError, type ListOut } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { errorMessage } from '$lib/errors';
  import HelpTip from '$lib/help/HelpTip.svelte';
  import { t } from '$lib/i18n.svelte';
  import { shortId } from './pin';

  interface Props {
    conceptId: string;
    versionId: string | null;
    /** Fires after a successful add (begreppssidans Listor-subvy uses this
     * to refresh its "lists containing this concept" view and count —
     * optional so every other call site is unaffected). */
    onadded?: () => void;
    /** Inline mode (2026-07-12): the flow renders immediately inside a
     * subview — no toggle button, no popover chrome. */
    inline?: boolean;
  }

  let { conceptId, versionId, onadded, inline = false }: Props = $props();

  // svelte-ignore state_referenced_locally — inline panels start open by design.
  let open = $state(inline);
  let loading = $state(false);
  let loadError = $state<string | null>(null);
  let lists = $state<ListOut[]>([]);

  let selectedListId = $state('');
  let createMode = $state(false);
  let newName = $state('');
  let newPurpose = $state('');
  let pinMode = $state<'pin' | 'follow'>('pin');

  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let savedTo = $state<ListOut | null>(null);

  let root = $state<HTMLElement | undefined>();
  let trigger = $state<HTMLButtonElement | undefined>();

  const effectivePin = $derived(versionId ? pinMode : 'follow');
  const canSave = $derived(
    !saving && (createMode ? newName.trim().length > 0 : selectedListId.length > 0)
  );

  function toggle(): void {
    if (open) {
      close();
      return;
    }
    open = true;
    savedTo = null;
    saveError = null;
    void loadLists();
  }

  // Inline mode renders open from the start — load the lists on mount.
  $effect(() => {
    if (inline) void loadLists();
  });

  function close(): void {
    open = false;
    trigger?.focus();
  }

  async function loadLists(): Promise<void> {
    loading = true;
    loadError = null;
    try {
      lists = await api.lists();
      if (lists.length === 0) {
        createMode = true;
      } else if (!selectedListId || !lists.some((l) => l.id === selectedListId)) {
        selectedListId = lists[0].id;
      }
    } catch (e) {
      loadError = errorMessage(e);
    } finally {
      loading = false;
    }
  }

  async function save(): Promise<void> {
    if (!canSave) return;
    saving = true;
    saveError = null;
    try {
      let target: ListOut;
      if (createMode) {
        target = await api.createList({
          name: newName.trim(),
          purpose: newPurpose.trim() || undefined
        });
        lists = [...lists, target];
      } else {
        const found = lists.find((l) => l.id === selectedListId);
        if (!found)
          throw new ApiError(404, { code: 'list_not_found', message: 'List not found' }, '/lists');
        target = found;
      }
      await api.addListItem(
        target.id,
        effectivePin === 'pin' && versionId
          ? { concept_id: conceptId, version_id: versionId, follow_head: false }
          : { concept_id: conceptId, follow_head: true }
      );
      savedTo = target;
      selectedListId = target.id;
      createMode = false;
      newName = '';
      newPurpose = '';
      onadded?.();
    } catch (e) {
      saveError = errorMessage(e);
    } finally {
      saving = false;
    }
  }

  function onWindowPointerDown(event: PointerEvent): void {
    if (!open) return;
    if (root && event.target instanceof Node && !root.contains(event.target)) open = false;
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (open && event.key === 'Escape') {
      event.preventDefault();
      close();
    }
  }

  function focusOnMount(node: HTMLElement): void {
    node.focus();
  }
</script>

<svelte:window onpointerdown={onWindowPointerDown} onkeydown={onWindowKeydown} />

<div class="addtolist ui" class:inline bind:this={root}>
  {#if !inline}
    <button
      class="btn"
      bind:this={trigger}
      onclick={toggle}
      aria-haspopup="dialog"
      aria-expanded={open}
    >
      <Icon name="pin" size={14} /> {t('list.add_button')}
    </button>
  {/if}

  {#if open}
    <div
      class="pop"
      class:card={!inline}
      role={inline ? 'group' : 'dialog'}
      aria-label={t('list.dialog_aria')}
      tabindex="-1"
      use:focusOnMount
    >
      {#if savedTo}
        <p class="done"><Icon name="check" size={14} /> {t('list.added_to')} <strong>{savedTo.name}</strong></p>
        <div class="row">
          <a class="btn btn-primary" href="/lists/{savedTo.id}">{t('list.view_list')}</a>
          <button class="btn btn-quiet" onclick={() => (savedTo = null)}>{t('list.add_more')}</button>
          <button class="btn btn-quiet" onclick={close}>{t('common.close')}</button>
        </div>
      {:else if loading}
        <p class="muted"><span class="spinner" aria-hidden="true"></span> {t('list.loading_lists')}</p>
      {:else if loadError}
        <p class="error" role="alert">{loadError}</p>
        <button class="btn" onclick={() => void loadLists()}>{t('common.retry')}</button>
      {:else}
        {#if !createMode && lists.length > 0}
          <fieldset>
            <legend>{t('list.choose_list')}</legend>
            <div class="list-picker">
              {#each lists as list (list.id)}
                <label class="pick">
                  <input type="radio" name="addtolist-list" value={list.id} bind:group={selectedListId} />
                  <span>{list.name}</span>
                  <span class="mono count">{(list.items ?? []).length}</span>
                </label>
              {/each}
            </div>
          </fieldset>
          <button class="btn btn-quiet new-toggle" onclick={() => (createMode = true)}>
            {t('list.new_list')}
          </button>
        {:else}
          <fieldset>
            <legend>{t('list.new_list_legend')}</legend>
            <label class="field">
              <span>{t('common.name')}</span>
              <input class="input" type="text" bind:value={newName} placeholder={t('list.name_placeholder')} />
            </label>
            <label class="field">
              <span>{t('list.purpose_label')} <span class="muted">{t('common.optional_paren')}</span></span>
              <input class="input" type="text" bind:value={newPurpose} placeholder={t('list.purpose_placeholder')} />
            </label>
          </fieldset>
          {#if lists.length > 0}
            <button class="btn btn-quiet new-toggle" onclick={() => (createMode = false)}>
              {t('list.choose_existing')}
            </button>
          {/if}
        {/if}

        <fieldset>
          <legend>{t('list.version_legend')} <HelpTip topic="pin-vs-follow" /></legend>
          <label class="pick" class:disabled={!versionId}>
            <input type="radio" name="addtolist-pin" value="pin" bind:group={pinMode} disabled={!versionId} />
            <span>
              {t('list.pin_this')}
              {#if versionId}<span class="mono count">{shortId(versionId)}</span>{/if}
              <small class="muted">{t('list.pin_hint')}</small>
            </span>
          </label>
          <label class="pick">
            <input type="radio" name="addtolist-pin" value="follow" bind:group={pinMode} />
            <span>
              {t('list.follow_latest')}
              <small class="muted">{t('list.follow_hint')}</small>
            </span>
          </label>
          {#if !versionId}
            <p class="muted note">{t('list.no_version_note')}</p>
          {/if}
        </fieldset>

        {#if saveError}
          <p class="error" role="alert">{saveError}</p>
        {/if}

        <div class="row">
          <button class="btn btn-primary" onclick={() => void save()} disabled={!canSave}>
            {#if saving}<span class="spinner" aria-hidden="true"></span> {t('common.saving')}{:else}{t('common.add')}{/if}
          </button>
          <button class="btn btn-quiet" onclick={close}>{t('common.cancel')}</button>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .addtolist {
    position: relative;
    display: inline-block;
  }

  /* Inline mode: the flow is part of the subview — no overlay chrome. */
  .addtolist.inline .pop {
    position: static;
    width: auto;
    max-width: 40ch;
    padding: 0;
    box-shadow: none;
    z-index: auto;
  }

  .pop {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 0;
    z-index: 60;
    width: min(340px, 86vw);
    padding: var(--space-4);
    box-shadow: var(--shadow-md);
    font-size: var(--text-sm);
  }

  .pop:focus {
    outline: none;
  }

  fieldset {
    border: none;
    margin: 0 0 var(--space-3);
    padding: 0;
  }

  legend {
    font-weight: 600;
    padding: 0;
    margin-bottom: var(--space-2);
  }

  .list-picker {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-height: 180px;
    overflow-y: auto;
  }

  .pick {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .pick:hover {
    background: var(--bg-sunken);
  }

  .pick.disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .pick input {
    accent-color: var(--accent);
  }

  .pick small {
    display: block;
    line-height: 1.35;
  }

  .count {
    color: var(--ink-3);
  }

  .field {
    display: block;
    margin-bottom: var(--space-2);
  }

  .field span {
    display: block;
    margin-bottom: var(--space-1);
    font-weight: 500;
  }

  .field input {
    width: 100%;
  }

  .new-toggle {
    margin-bottom: var(--space-3);
    padding-left: var(--space-2);
  }

  .row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .done {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    margin-bottom: var(--space-3);
    color: var(--ins-strong);
  }

  .muted {
    color: var(--ink-3);
  }

  .note {
    margin: var(--space-1) 0 0;
    font-size: var(--text-xs);
  }

  .error {
    margin: 0 0 var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-sm);
    background: var(--del-wash);
  }

  .spinner {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    border: 2px solid var(--line);
    border-top-color: var(--accent);
    border-radius: var(--radius-round);
    vertical-align: -0.1em;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
