<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import {
    adminUsers,
    api,
    suspendOrg,
    unsuspendOrg,
    type OrgMemberOut,
    type OrgOut,
    type OrgType
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { slugify } from '$lib/slug';
  import { currentUser, isOrgAdmin, setSession } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  let orgs = $state<OrgOut[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);

  // Skapa organisation
  let newName = $state('');
  let newSlug = $state('');
  let newType = $state<OrgType>('industry_association');
  let slugTouched = $state(false);
  let creating = $state(false);

  // Lägg till medlem — ett formulär per org-kort (multi-org).
  let addForms = $state<Record<string, { handle: string; role: string; kind: string }>>({});
  let adding = $state<string | null>(null);

  const ROLES = ['admin', 'editor', 'viewer'] as const;
  const KINDS = ['member', 'guest'] as const;
  const ORG_TYPES: OrgType[] = ['industry_association', 'academy', 'commercial'];

  function roleLabel(role: string): string {
    if (role === 'admin') return t('orgs.role_admin');
    if (role === 'editor') return t('orgs.role_editor');
    if (role === 'viewer') return t('orgs.role_viewer');
    return role;
  }

  function kindLabel(kind: string): string {
    return kind === 'guest' ? t('orgs.kind_guest') : t('orgs.kind_member');
  }

  function typeLabel(type: string | null | undefined): string {
    if (type === 'commercial') return t('orgs.type_commercial');
    if (type === 'academy') return t('orgs.type_academy');
    if (type === 'industry_association') return t('orgs.type_industry');
    return t('orgs.type_unset');
  }

  // Pure read + explicit write — never mutate $state during render.
  function formOf(orgId: string): { handle: string; role: string; kind: string } {
    return addForms[orgId] ?? { handle: '', role: 'editor', kind: 'member' };
  }

  function updateForm(
    orgId: string,
    patch: Partial<{ handle: string; role: string; kind: string }>
  ): void {
    addForms[orgId] = { ...formOf(orgId), ...patch };
  }

  const ownsOrg = $derived(currentUser.memberships.some((m) => m.is_owner));
  const canManageOrg = (org: OrgOut) => currentUser.is_super_admin || isOrgAdmin(org.id);
  const myMembership = (org: OrgOut) => currentUser.memberships.find((m) => m.id === org.id);

  async function refresh(): Promise<void> {
    loading = true;
    loadError = null;
    try {
      if (currentUser.token) {
        // Membership may have changed since login — refresh the session.
        const me = await api.me();
        setSession({
          handle: me.handle,
          display_name: me.display_name,
          token: currentUser.token,
          is_super_admin: me.is_super_admin,
          review_status: me.review_status ?? 'approved',
          memberships: (me.memberships ?? []).map((m) => ({
            ...m,
            role: m.role as 'admin' | 'editor' | 'viewer'
          }))
        });
      }
      orgs = currentUser.handle ? await api.orgs() : [];
    } catch (e) {
      loadError = errorMessage(e);
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  function replaceOrg(updated: OrgOut): void {
    orgs = orgs.map((o) => (o.id === updated.id ? updated : o));
  }

  async function createOrg(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    actionError = null;
    if (!newName.trim() || !newSlug.trim()) {
      actionError = t('orgs.error_name_slug');
      return;
    }
    creating = true;
    try {
      await api.createOrg({ name: newName.trim(), slug: newSlug.trim(), org_type: newType });
      newName = '';
      newSlug = '';
      slugTouched = false;
      await refresh();
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      creating = false;
    }
  }

  async function addMember(event: SubmitEvent, org: OrgOut): Promise<void> {
    event.preventDefault();
    const form = formOf(org.id);
    if (!form.handle.trim()) return;
    actionError = null;
    adding = org.id;
    try {
      replaceOrg(
        await api.addOrgMember(org.slug, {
          handle: form.handle.trim(),
          role: form.role,
          kind: form.kind
        })
      );
      updateForm(org.id, { handle: '' });
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      adding = null;
    }
  }

  async function changeMember(
    org: OrgOut,
    userId: string,
    payload: { role?: string; kind?: string }
  ): Promise<void> {
    actionError = null;
    try {
      replaceOrg(await api.patchOrgMember(org.slug, userId, payload));
    } catch (e) {
      actionError = errorMessage(e);
      // Roll back the select to server state.
      orgs = [...orgs];
    }
  }

  // Borttagning sker direkt med inline-ångra (designmanualen: undo, aldrig
  // confirm()). Handle + roll + typ räcker för att återinsätta via addOrgMember.
  let removedMember = $state<{
    orgId: string;
    orgSlug: string;
    handle: string;
    name: string;
    role: string;
    kind: string;
  } | null>(null);
  let undoBusy = $state(false);
  let undoTimer: ReturnType<typeof setTimeout> | null = null;

  async function removeMember(org: OrgOut, member: OrgMemberOut): Promise<void> {
    actionError = null;
    try {
      await api.removeOrgMember(org.slug, member.user_id);
      removedMember = {
        orgId: org.id,
        orgSlug: org.slug,
        handle: member.handle,
        name: member.display_name,
        role: member.role,
        kind: member.kind
      };
      if (undoTimer) clearTimeout(undoTimer);
      undoTimer = setTimeout(() => (removedMember = null), 6000);
      await refresh();
    } catch (e) {
      actionError = errorMessage(e);
    }
  }

  async function undoRemove(): Promise<void> {
    if (!removedMember || undoBusy) return;
    undoBusy = true;
    try {
      replaceOrg(
        await api.addOrgMember(removedMember.orgSlug, {
          handle: removedMember.handle,
          role: removedMember.role,
          kind: removedMember.kind
        })
      );
      removedMember = null;
      if (undoTimer) clearTimeout(undoTimer);
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      undoBusy = false;
    }
  }

  onDestroy(() => {
    if (undoTimer) clearTimeout(undoTimer);
  });

  // Egen synlighet (beslut 4): per-medlemskaps-opt-out från författarsidan.
  let visibilityBusy = $state<string | null>(null);

  async function toggleMyVisibility(org: OrgOut, isPublic: boolean): Promise<void> {
    actionError = null;
    visibilityBusy = org.id;
    try {
      replaceOrg(await api.patchMyMembership(org.slug, isPublic));
      const mine = currentUser.memberships.find((m) => m.id === org.id);
      if (mine) mine.is_public = isPublic;
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      visibilityBusy = null;
    }
  }

  // Superadmin: godkännande bekräftar organisationstypen (beslut 3).
  let approveTypes = $state<Record<string, OrgType>>({});

  async function approve(org: OrgOut): Promise<void> {
    actionError = null;
    try {
      const chosen = approveTypes[org.id] ?? (org.org_type as OrgType) ?? 'industry_association';
      replaceOrg(await api.approveOrg(org.slug, { org_type: chosen }));
    } catch (e) {
      actionError = errorMessage(e);
    }
  }

  // Ägarskifte (superadmin): ägaren är det ekonomiska ankaret — ny ägare
  // anges med användarnamn, blir admin-medlem och kan bara äga en org
  // (servern vägrar annars). Inline-formulär i tabellraden, aldrig confirm().
  let ownerPendingSlug = $state<string | null>(null);
  let ownerHandle = $state('');
  let ownerBusy = $state(false);

  function ownerHandleOf(org: OrgOut): string | null {
    if (!org.owner_user_id) return null;
    return org.members.find((m) => m.user_id === org.owner_user_id)?.handle ?? null;
  }

  async function transferOwner(org: OrgOut): Promise<void> {
    const handle = ownerHandle.trim().toLowerCase();
    if (!handle || ownerBusy) return;
    ownerBusy = true;
    actionError = null;
    try {
      let userId = org.members.find((m) => m.handle === handle)?.user_id;
      if (!userId) {
        const matches = await adminUsers(handle);
        userId = matches.find((u) => u.handle === handle)?.id;
      }
      if (!userId) {
        actionError = t('orgs.transfer_user_not_found', { handle });
        return;
      }
      replaceOrg(await api.transferOrgOwner(org.slug, userId));
      ownerPendingSlug = null;
      ownerHandle = '';
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      ownerBusy = false;
    }
  }

  // Suspension (guardrail G4): avstängning kräver att sluggen skrivs in —
  // återaktivering är återställande och behåller ja/avbryt.
  let suspendPendingSlug = $state<string | null>(null);
  let suspendTyped = $state('');
  let suspendBusy = $state(false);

  async function applySuspension(org: OrgOut): Promise<void> {
    if (!org.is_suspended && suspendTyped.trim() !== org.slug) return;
    actionError = null;
    suspendBusy = true;
    try {
      replaceOrg(org.is_suspended ? await unsuspendOrg(org.slug) : await suspendOrg(org.slug));
      suspendPendingSlug = null;
      suspendTyped = '';
    } catch (e) {
      actionError = errorMessage(e);
    } finally {
      suspendBusy = false;
    }
  }
</script>

<svelte:head><title>{t('orgs.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('orgs.h1')} intro={t('orgs.intro')} />

  {#if !currentUser.handle}
    <p class="locked ui" role="status">
      {t('orgs.locked')}
    </p>
  {:else if loading}
    <p class="ui muted">{t('orgs.loading')}</p>
  {:else}
    {#if loadError}
      <p class="error ui" role="alert">{t('orgs.load_error', { error: loadError })}</p>
    {/if}
    {#if actionError}
      <p class="error ui" role="alert">{actionError}</p>
    {/if}

    {#if !currentUser.is_super_admin}
      {#if currentUser.memberships.length === 0}
        <p class="muted ui">{t('orgs.no_memberships')}</p>
      {/if}

      {#each orgs.filter((o) => myMembership(o)) as org (org.id)}
        {@const mine = myMembership(org)}
        <section class="card org-card">
          <header class="org-head">
            <h2>{org.name}</h2>
            <p class="mono meta">
              /{org.slug} · {org.members.length}
              {org.members.length === 1 ? t('orgs.member_singular') : t('orgs.members')}
              {#if !org.is_approved}
                · <span class="pending">{t('orgs.pending_approval')}</span>
              {/if}
              {#if org.is_suspended}
                · <span class="pending">{t('orgs.suspended_note')}</span>
              {/if}
            </p>
            <p class="pills">
              {#if mine}
                <span class="pill">{roleLabel(mine.role)}</span>
                {#if mine.kind === 'guest'}<span class="pill">{t('orgs.kind_guest')}</span>{/if}
                {#if mine.is_owner}<span class="pill owner">{t('orgs.owner_pill')}</span>{/if}
              {/if}
              {#if org.org_type}
                <span class="pill">{typeLabel(org.org_type)}</span>
                {#if org.org_type === 'commercial'}
                  <span class="pill billing">{t('orgs.type_billing_note')}</span>
                {:else}
                  <span class="pill exempt">{t('orgs.type_exempt_note')}</span>
                {/if}
              {/if}
            </p>
          </header>

          <table class="ui members" aria-label={t('orgs.members_aria')}>
            <thead>
              <tr>
                <th>{t('orgs.th_member')}</th>
                <th>{t('orgs.th_handle')}</th>
                <th>{t('orgs.th_role')}</th>
                <th>{t('orgs.th_kind')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each org.members as member (member.user_id)}
                {@const isOwner = org.owner_user_id === member.user_id}
                <tr>
                  <td>
                    {member.display_name}
                    {#if isOwner}<span class="pill owner">{t('orgs.owner_pill')}</span>{/if}
                  </td>
                  <td class="mono"><a href={`/authors/${member.handle}`}>{member.handle}</a></td>
                  <td>
                    {#if canManageOrg(org) && !isOwner}
                      <select
                        class="input"
                        value={member.role}
                        aria-label={t('orgs.role_for_aria', { name: member.display_name })}
                        onchange={(e) =>
                          changeMember(org, member.user_id, { role: e.currentTarget.value })}
                      >
                        {#each ROLES as role (role)}
                          <option value={role}>{roleLabel(role)}</option>
                        {/each}
                      </select>
                    {:else}
                      {roleLabel(member.role)}
                    {/if}
                  </td>
                  <td>
                    {#if canManageOrg(org) && !isOwner}
                      <select
                        class="input"
                        value={member.kind}
                        aria-label={t('orgs.kind_for_aria', { name: member.display_name })}
                        onchange={(e) =>
                          changeMember(org, member.user_id, { kind: e.currentTarget.value })}
                      >
                        {#each KINDS as kind (kind)}
                          <option value={kind}>{kindLabel(kind)}</option>
                        {/each}
                      </select>
                    {:else}
                      {kindLabel(member.kind)}
                    {/if}
                  </td>
                  <td class="right">
                    {#if canManageOrg(org) && !isOwner}
                      <button
                        type="button"
                        class="btn btn-quiet danger"
                        onclick={() => removeMember(org, member)}
                      >
                        {t('orgs.remove')}
                      </button>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>

          {#if removedMember && removedMember.orgId === org.id}
            <p class="undo-row ui" role="status">
              <span>{t('orgs.removed_member', { name: removedMember.name })}</span>
              <button type="button" class="btn btn-quiet" onclick={undoRemove} disabled={undoBusy}>
                {undoBusy ? t('common.saving') : t('orgs.undo')}
              </button>
            </p>
          {/if}

          {#if canManageOrg(org)}
            <form
              class="add-member"
              onsubmit={(e) => addMember(e, org)}
              aria-label={t('orgs.add_member_aria')}
            >
              <div class="field grow">
                <label for={`org-add-handle-${org.id}`}>{t('orgs.add_member_label')}</label>
                <input
                  id={`org-add-handle-${org.id}`}
                  class="input"
                  type="text"
                  value={formOf(org.id).handle}
                  oninput={(e) => updateForm(org.id, { handle: e.currentTarget.value })}
                  placeholder={t('orgs.add_handle_placeholder')}
                  spellcheck="false"
                />
              </div>
              <div class="field">
                <label for={`org-add-role-${org.id}`}>{t('orgs.th_role')}</label>
                <select
                  id={`org-add-role-${org.id}`}
                  class="input"
                  value={formOf(org.id).role}
                  onchange={(e) => updateForm(org.id, { role: e.currentTarget.value })}
                >
                  {#each ROLES as role (role)}
                    <option value={role}>{roleLabel(role)}</option>
                  {/each}
                </select>
              </div>
              <div class="field">
                <label for={`org-add-kind-${org.id}`}>{t('orgs.th_kind')}</label>
                <select
                  id={`org-add-kind-${org.id}`}
                  class="input"
                  value={formOf(org.id).kind}
                  onchange={(e) => updateForm(org.id, { kind: e.currentTarget.value })}
                >
                  {#each KINDS as kind (kind)}
                    <option value={kind}>{kindLabel(kind)}</option>
                  {/each}
                </select>
              </div>
              <button
                type="submit"
                class="btn"
                disabled={adding === org.id || !formOf(org.id).handle.trim()}
              >
                {adding === org.id ? t('common.adding') : t('common.add')}
              </button>
            </form>
          {/if}

          {#if mine}
            <label class="visibility ui">
              <input
                type="checkbox"
                checked={mine.is_public}
                disabled={visibilityBusy === org.id}
                onchange={(e) => toggleMyVisibility(org, e.currentTarget.checked)}
              />
              {t('orgs.visibility_label')}
            </label>
          {/if}
        </section>
      {/each}
    {/if}

    {#if !currentUser.is_super_admin && !ownsOrg}
      <section class="card org-card">
        <h2>{t('orgs.create_h2')}</h2>
        <p class="muted ui">
          {t('orgs.create_desc')}
        </p>
        <p class="muted ui funnel-note">
          {t('orgs.create_funnel_note')}
        </p>
        <form class="create" onsubmit={createOrg} aria-label={t('orgs.create_h2')}>
          <div class="field">
            <label for="org-name">{t('common.name')}</label>
            <input
              id="org-name"
              class="input"
              type="text"
              bind:value={newName}
              placeholder={t('orgs.name_placeholder')}
              oninput={() => {
                if (!slugTouched) newSlug = slugify(newName);
              }}
            />
          </div>
          <div class="field">
            <label for="org-slug">{t('orgs.th_slug')}</label>
            <input
              id="org-slug"
              class="input"
              type="text"
              bind:value={newSlug}
              placeholder={t('orgs.slug_placeholder')}
              spellcheck="false"
              oninput={() => (slugTouched = true)}
            />
          </div>
          <div class="field">
            <label for="org-type">{t('orgs.create_type_label')}</label>
            <select id="org-type" class="input" bind:value={newType}>
              {#each ORG_TYPES as orgType (orgType)}
                <option value={orgType}>{typeLabel(orgType)}</option>
              {/each}
            </select>
            <p class="muted ui type-note">
              {#if newType === 'commercial'}
                {t('orgs.type_note_commercial')}
              {:else}
                {t('orgs.type_note_noncommercial')}
              {/if}
            </p>
          </div>
          <button type="submit" class="btn btn-primary" disabled={creating}>
            {creating ? t('common.creating') : t('orgs.create_btn')}
          </button>
        </form>
      </section>
    {/if}

    {#if currentUser.is_super_admin}
      <section class="all-orgs">
        <h2 class="ui section-title">{t('orgs.all_h2')}</h2>
        {#if orgs.length === 0}
          <p class="muted ui">{t('orgs.none')}</p>
        {:else}
          <table class="ui members" aria-label={t('orgs.all_h2')}>
            <thead>
              <tr>
                <th>{t('orgs.th_org')}</th>
                <th>{t('orgs.th_slug')}</th>
                <th>{t('orgs.th_members')}</th>
                <th>{t('orgs.th_owner')}</th>
                <th>{t('orgs.th_type')}</th>
                <th>{t('common.status')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each orgs as org (org.id)}
                <tr>
                  <td>{org.name}</td>
                  <td class="mono">{org.slug}</td>
                  <td>{org.members.length}</td>
                  <td class="owner-cell">
                    {#if ownerPendingSlug === org.slug}
                      <span
                        class="owner-form"
                        role="group"
                        aria-label={t('orgs.transfer_owner_aria', { name: org.name })}
                      >
                        <input
                          type="text"
                          class="input mono owner-input"
                          bind:value={ownerHandle}
                          placeholder={t('orgs.add_handle_placeholder')}
                          spellcheck="false"
                          aria-label={t('orgs.transfer_owner_label')}
                        />
                        <button
                          type="button"
                          class="btn btn-quiet"
                          disabled={ownerBusy || !ownerHandle.trim()}
                          onclick={() => transferOwner(org)}
                        >
                          {ownerBusy ? t('common.saving') : t('orgs.transfer_confirm')}
                        </button>
                        <button
                          type="button"
                          class="btn btn-quiet"
                          disabled={ownerBusy}
                          onclick={() => {
                            ownerPendingSlug = null;
                            ownerHandle = '';
                          }}
                        >
                          {t('common.cancel')}
                        </button>
                      </span>
                    {:else}
                      {#if ownerHandleOf(org)}
                        <a class="mono" href={`/authors/${ownerHandleOf(org)}`}
                          >{ownerHandleOf(org)}</a
                        >
                      {:else}
                        <span class="muted">{t('orgs.owner_none')}</span>
                      {/if}
                      <button
                        type="button"
                        class="btn btn-quiet"
                        onclick={() => {
                          ownerPendingSlug = org.slug;
                          ownerHandle = '';
                          actionError = null;
                        }}
                        title={t('orgs.transfer_owner_title')}
                      >
                        {t('orgs.transfer_owner')}
                      </button>
                    {/if}
                  </td>
                  <td>
                    {#if org.is_approved}
                      {typeLabel(org.org_type)}
                    {:else}
                      <select
                        class="input"
                        aria-label={t('orgs.type_for_aria', { name: org.name })}
                        value={approveTypes[org.id] ?? org.org_type ?? 'industry_association'}
                        onchange={(e) => (approveTypes[org.id] = e.currentTarget.value as OrgType)}
                      >
                        {#each ORG_TYPES as orgType (orgType)}
                          <option value={orgType}>{typeLabel(orgType)}</option>
                        {/each}
                      </select>
                    {/if}
                  </td>
                  <td>
                    {#if org.is_approved}{t('orgs.approved')}{:else}<span class="pending"
                        >{t('orgs.waiting')}</span
                      >{/if}
                    {#if org.is_suspended}
                      <span class="suspended-badge">{t('orgs.suspended_badge')}</span>
                    {/if}
                  </td>
                  <td class="right">
                    {#if !org.is_approved}
                      <button type="button" class="btn" onclick={() => approve(org)}>
                        {t('orgs.approve')}
                      </button>
                    {/if}
                    {#if suspendPendingSlug === org.slug}
                      <span class="suspend-confirm" role="alert">
                        {#if org.is_suspended}
                          {t('orgs.reactivate_confirm', { name: org.name })}
                        {:else}
                          {t('orgs.suspend_confirm_slug', { slug: org.slug })}
                          <input
                            type="text"
                            class="input slug-confirm mono"
                            bind:value={suspendTyped}
                            placeholder={org.slug}
                            spellcheck="false"
                            aria-label={t('orgs.suspend_confirm_slug', { slug: org.slug })}
                          />
                        {/if}
                        <button
                          type="button"
                          class="btn btn-quiet"
                          class:danger={!org.is_suspended}
                          disabled={suspendBusy ||
                            (!org.is_suspended && suspendTyped.trim() !== org.slug)}
                          onclick={() => applySuspension(org)}
                        >
                          {suspendBusy ? t('common.saving') : t('common.yes')}
                        </button>
                        <button
                          type="button"
                          class="btn btn-quiet"
                          disabled={suspendBusy}
                          onclick={() => {
                            suspendPendingSlug = null;
                            suspendTyped = '';
                          }}
                        >
                          {t('common.cancel')}
                        </button>
                      </span>
                    {:else}
                      <button
                        type="button"
                        class="btn btn-quiet"
                        class:danger={!org.is_suspended}
                        onclick={() => {
                          suspendPendingSlug = org.slug;
                          suspendTyped = '';
                          actionError = null;
                        }}
                        title={org.is_suspended
                          ? t('orgs.reactivate_title')
                          : t('orgs.suspend_title')}
                      >
                        {org.is_suspended ? t('orgs.reactivate') : t('orgs.suspend')}
                      </button>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>
    {/if}
  {/if}
</div>

<style>

  .locked {
    max-width: 65ch;
    padding: var(--space-3) var(--space-4);
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .muted {
    color: var(--ink-3);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin-bottom: var(--space-4);
  }

  .org-card {
    max-width: 760px;
    padding: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .org-head h2 {
    margin-bottom: var(--space-1);
  }

  .meta {
    color: var(--ink-3);
    margin-bottom: var(--space-2);
  }

  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
  }

  .owner {
    border-color: var(--accent);
    color: var(--accent);
  }

  .billing {
    border-color: var(--del-strong);
    color: var(--del-strong);
  }

  .exempt {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .pending {
    color: var(--del-strong);
  }

  .suspended-badge {
    display: inline-block;
    margin-left: var(--space-1);
    font-size: var(--text-xs);
    border: 1px solid var(--del-strong);
    color: var(--del-strong);
    border-radius: var(--radius-pill);
    padding: 0.05em 0.55em;
    white-space: nowrap;
  }

  .suspend-confirm {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--ink-2);
    max-width: 46ch;
    text-align: left;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .slug-confirm {
    width: 12ch;
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    /* .input (later in app.css) would otherwise beat the .mono utility. */
    font-family: var(--font-mono);
  }

  .owner-cell {
    white-space: nowrap;
  }

  .owner-form {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    flex-wrap: wrap;
  }

  .owner-input {
    width: 14ch;
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    /* .input (later in app.css) would otherwise beat the .mono utility. */
    font-family: var(--font-mono);
  }

  .members {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    margin-bottom: var(--space-4);
  }

  .members th {
    text-align: left;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    padding: var(--space-2);
    border-bottom: 1px solid var(--line);
  }

  .members td {
    padding: var(--space-2);
    border-bottom: 1px solid var(--line);
  }

  .members td .owner {
    margin-left: var(--space-1);
  }

  .right {
    text-align: right;
  }

  .danger:hover {
    color: var(--del-strong);
  }

  .undo-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-sunken);
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin-bottom: var(--space-4);
  }

  .add-member {
    display: flex;
    gap: var(--space-3);
    align-items: flex-end;
    flex-wrap: wrap;
  }

  .visibility {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-4);
    font-size: var(--text-sm);
    color: var(--ink-2);
    text-transform: none;
    font-weight: 400;
    letter-spacing: normal;
  }

  .visibility input {
    width: auto;
  }

  .create {
    max-width: 420px;
  }

  .funnel-note {
    max-width: 60ch;
    font-size: var(--text-sm);
    margin-bottom: var(--space-4);
  }

  .type-note {
    font-size: var(--text-xs);
    margin-top: var(--space-1);
  }

  .field {
    margin-bottom: var(--space-3);
  }

  .grow {
    flex: 1;
    min-width: 220px;
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

  input,
  select {
    width: 100%;
  }

  .add-member button,
  .members select {
    width: auto;
  }

  .section-title {
    margin: var(--space-6) 0 var(--space-4);
  }

  .all-orgs {
    max-width: 920px;
  }
</style>
