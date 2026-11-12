<script lang="ts">
  /** An organisation's flag on ONE version — "this is the definition we use"
   * (VISION §4.3, rework 2026-07-11): list of stamps, a "Fastställ för <org>"
   * mini-form, and withdraw-with-note. Stamping is shown only to admins of an
   * organisation (the stamp is made on the org's behalf — the server also
   * requires the org to be approved); withdrawal only to the endorsing org's
   * admins and super admins. */
  import { endorse, withdrawEndorsement, type EndorsementOut } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { adminOrgs, currentUser, isOrgAdmin } from '$lib/user.svelte';

  interface Props {
    versionId: string;
    endorsements: EndorsementOut[];
    /** Called after a successful write so the owner refetches its data. */
    onchanged: () => void;
  }

  let { versionId, endorsements, onchanged }: Props = $props();

  // Multi-org (2026-07): admin i minst en org får stämpla; med flera väljs
  // den agerande organisationen i formuläret (servern kräver den explicit).
  const myAdminOrgs = $derived(adminOrgs());
  const canStamp = $derived(myAdminOrgs.length > 0);
  const idBase = $derived(`endorse-${versionId.slice(0, 8)}`);

  function canWithdraw(endorsement: EndorsementOut): boolean {
    if (currentUser.is_super_admin) return true;
    return endorsement.organisation !== null && isOrgAdmin(endorsement.organisation.id);
  }

  // Fastställ-form
  let formOpen = $state(false);
  let note = $state('');
  let actingOrgId = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const actingOrgName = $derived(
    myAdminOrgs.find((o) => o.id === actingOrgId)?.name ?? myAdminOrgs[0]?.name ?? ''
  );

  // Återkalla-form (one at a time)
  let withdrawingId = $state<string | null>(null);
  let withdrawNote = $state('');
  let withdrawing = $state(false);
  let withdrawError = $state<string | null>(null);

  function openForm(): void {
    note = '';
    error = null;
    actingOrgId = myAdminOrgs[0]?.id ?? '';
    formOpen = true;
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    if (!note.trim()) {
      error = t('endorse.error_no_note');
      return;
    }
    saving = true;
    try {
      await endorse(versionId, {
        note: note.trim(),
        ...(actingOrgId ? { organisation_id: actingOrgId } : {})
      });
      formOpen = false;
      onchanged();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      saving = false;
    }
  }

  function openWithdraw(id: string): void {
    withdrawingId = id;
    withdrawNote = '';
    withdrawError = null;
  }

  async function submitWithdraw(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!withdrawingId) return;
    withdrawError = null;
    if (!withdrawNote.trim()) {
      withdrawError = t('endorse.error_no_withdraw_note');
      return;
    }
    withdrawing = true;
    try {
      await withdrawEndorsement(withdrawingId, { note: withdrawNote.trim() });
      withdrawingId = null;
      onchanged();
    } catch (e) {
      withdrawError = errorMessage(e);
    } finally {
      withdrawing = false;
    }
  }
</script>

<div class="endorse ui">
  {#each endorsements as endorsement (endorsement.id)}
    <div class="entry" class:withdrawn={endorsement.withdrawn_at !== null}>
      <p class="line">
        <span class="body-text"
          ><Icon name="star" filled size={14} /> {t('endorse.by')} {endorsement.body}
          <span class="mono when">{formatDate(endorsement.created_at)}</span></span
        >
        {#if !endorsement.withdrawn_at && canWithdraw(endorsement) && withdrawingId !== endorsement.id}
          <button
            type="button"
            class="btn btn-quiet withdraw-btn"
            onclick={() => openWithdraw(endorsement.id)}
            title={t('endorse.withdraw_title')}
          >
            {t('endorse.withdraw')}
          </button>
        {/if}
      </p>
      {#if endorsement.note}
        <p class="note">”{endorsement.note}”</p>
      {/if}
      {#if endorsement.withdrawn_at}
        <p class="withdrawal">
          {t('endorse.withdrawn')} {formatDate(endorsement.withdrawn_at)}{#if endorsement.withdrawal_note}
            {t('typo.dash')} ”{endorsement.withdrawal_note}”{/if}
        </p>
      {/if}

      {#if withdrawingId === endorsement.id}
        <form class="mini-form" onsubmit={submitWithdraw} aria-label={t('endorse.withdraw_form_aria')}>
          <label for="{idBase}-withdraw-note">{t('endorse.note_required_label')}</label>
          <textarea
            id="{idBase}-withdraw-note"
            class="input"
            rows="2"
            bind:value={withdrawNote}
            disabled={withdrawing}
            placeholder={t('endorse.withdraw_note_placeholder')}
            required
          ></textarea>
          {#if withdrawError}
            <p class="error" role="alert">{withdrawError}</p>
          {/if}
          <div class="actions">
            <button type="submit" class="btn-danger" disabled={withdrawing}>
              {withdrawing ? t('endorse.withdrawing') : t('endorse.withdraw_confirm')}
            </button>
            <button
              type="button"
              class="btn btn-quiet"
              disabled={withdrawing}
              onclick={() => (withdrawingId = null)}
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      {/if}
    </div>
  {/each}

  {#if canStamp}
    {#if !formOpen}
      <button
        type="button"
        class="btn endorse-btn"
        onclick={openForm}
        title={t('endorse.button_title')}
      >
        <Icon name="star" filled size={14} /> {myAdminOrgs.length === 1
          ? t('endorse.button_for_org', { org: myAdminOrgs[0].name })
          : t('endorse.button_generic')}
      </button>
    {:else}
      <form class="mini-form" onsubmit={submit} aria-label={t('endorse.form_aria')}>
        {#if myAdminOrgs.length > 1}
          <label for="{idBase}-org">{t('endorse.acting_org_label')}</label>
          <select id="{idBase}-org" class="input" bind:value={actingOrgId} disabled={saving}>
            {#each myAdminOrgs as org (org.id)}
              <option value={org.id}>{org.name}</option>
            {/each}
          </select>
        {:else}
          <p class="as-org">{t('endorse.stamping_as', { org: actingOrgName })}</p>
        {/if}
        <label for="{idBase}-note">{t('endorse.note_required_label')}</label>
        <textarea
          id="{idBase}-note"
          class="input"
          rows="2"
          bind:value={note}
          disabled={saving}
          placeholder={t('endorse.note_placeholder')}
          required
        ></textarea>
        {#if error}
          <p class="error" role="alert">{error}</p>
        {/if}
        <div class="actions">
          <button type="submit" class="btn btn-primary" disabled={saving}>
            {saving ? t('endorse.endorsing') : t('endorse.confirm')}
          </button>
          <button
            type="button"
            class="btn btn-quiet"
            disabled={saving}
            onclick={() => (formOpen = false)}
          >
            {t('common.cancel')}
          </button>
        </div>
      </form>
    {/if}
  {/if}
</div>

<style>
  .endorse {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }

  .entry .line {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: 0;
  }

  .body-text {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    color: var(--endorsed);
    font-weight: 500;
  }

  .withdrawn .body-text {
    text-decoration: line-through;
    opacity: 0.6;
  }

  .when {
    color: var(--ink-3);
    font-weight: 400;
  }

  .note {
    margin: 0;
    padding-left: var(--space-3);
    border-left: 3px solid var(--endorsed);
    font-family: var(--font-serif);
    font-style: italic;
    color: var(--ink-2);
  }

  .withdrawn .note {
    opacity: 0.6;
  }

  .withdrawal {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  .withdraw-btn {
    font-size: var(--text-xs);
    padding: 0.2em 0.6em;
  }

  .endorse-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    align-self: flex-start;
    border-color: var(--endorsed);
    color: var(--endorsed);
  }

  .endorse-btn:hover {
    background: var(--endorsed);
    color: var(--bg);
  }

  .mini-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-top: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg);
  }

  .mini-form label {
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .mini-form textarea,
  .mini-form select {
    width: 100%;
    margin-bottom: var(--space-2);
  }

  .as-org {
    font-size: var(--text-xs);
    color: var(--ink-2);
    margin: 0 0 var(--space-2);
  }

  .error {
    margin: 0 0 var(--space-2);
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
</style>
