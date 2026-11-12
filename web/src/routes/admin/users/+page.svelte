<script lang="ts">
  /** Admin user management (iteration 3). Super admin only — the guard mirrors
   * /admin/outreach. Self-actions (inaktivera, superadmin) are hidden;
   * the server enforces the same rule. Reset links are one-time, 24 h. */
  import {
    adminResetLink,
    adminUsers,
    ApiError,
    patchAdminUser,
    type AdminUserFilter,
    type AdminUserOut
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  type ConfirmAction = 'deactivate' | 'grant' | 'revoke';

  let rows = $state<AdminUserOut[]>([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let denied = $state(false);

  let q = $state('');
  let filter = $state<AdminUserFilter>('all');

  let busyId = $state<string | null>(null);
  let rowErrors = $state<Record<string, string>>({});
  let confirming = $state<{ id: string; action: ConfirmAction } | null>(null);
  let resetLinkFor = $state<string | null>(null);
  let resetLink = $state<{ url: string; expires_at: string } | null>(null);
  let copied = $state(false);

  const allowed = $derived(currentUser.is_super_admin);

  const FILTERS: { value: AdminUserFilter; label: string }[] = $derived([
    { value: 'all', label: t('au.filter_all') },
    { value: 'active', label: t('au.filter_active') },
    { value: 'inactive', label: t('au.filter_inactive') },
    { value: 'admins', label: t('au.filter_admins') },
    { value: 'pending', label: t('au.filter_pending') }
  ]);

  function roleLabel(role: string): string {
    if (role === 'admin') return t('orgs.role_admin');
    if (role === 'editor') return t('orgs.role_editor');
    if (role === 'viewer') return t('orgs.role_viewer');
    return role;
  }

  const CONFIRM_TEXTS: Record<ConfirmAction, { question: string; yes: string }> = $derived({
    deactivate: { question: t('au.confirm_deactivate_q'), yes: t('au.confirm_deactivate_yes') },
    grant: { question: t('au.confirm_grant_q'), yes: t('au.confirm_grant_yes') },
    revoke: { question: t('au.confirm_revoke_q'), yes: t('au.confirm_revoke_yes') }
  });

  async function load(query: string, f: AdminUserFilter): Promise<void> {
    loadError = null;
    try {
      rows = await adminUsers(query, f);
      loaded = true;
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) denied = true;
      else loadError = errorMessage(e);
    }
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    if (!allowed) return;
    const query = q.trim();
    const f = filter;
    clearTimeout(timer);
    timer = setTimeout(() => void load(query, f), query ? 220 : 0);
  });

  function isSelf(row: AdminUserOut): boolean {
    return row.handle === currentUser.handle;
  }

  function clearRowError(id: string): void {
    const { [id]: _removed, ...rest } = rowErrors;
    rowErrors = rest;
  }

  async function patchRow(
    row: AdminUserOut,
    payload: { is_active?: boolean; is_super_admin?: boolean; review_status?: string }
  ): Promise<void> {
    busyId = row.id;
    clearRowError(row.id);
    try {
      const updated = await patchAdminUser(row.id, payload);
      rows = rows.map((r) => (r.id === row.id ? updated : r));
      confirming = null;
    } catch (e) {
      rowErrors = { ...rowErrors, [row.id]: errorMessage(e) };
    } finally {
      busyId = null;
    }
  }

  function confirmPayload(action: ConfirmAction): { is_active?: boolean; is_super_admin?: boolean } {
    if (action === 'deactivate') return { is_active: false };
    return { is_super_admin: action === 'grant' };
  }

  async function makeResetLink(row: AdminUserOut): Promise<void> {
    busyId = row.id;
    clearRowError(row.id);
    copied = false;
    try {
      const link = await adminResetLink(row.id);
      resetLink = {
        url: link.url.startsWith('http') ? link.url : window.location.origin + link.url,
        expires_at: link.expires_at
      };
      resetLinkFor = row.id;
    } catch (e) {
      rowErrors = { ...rowErrors, [row.id]: errorMessage(e) };
    } finally {
      busyId = null;
    }
  }

  async function copyLink(rowId: string): Promise<void> {
    if (!resetLink) return;
    clearRowError(rowId);
    try {
      await navigator.clipboard.writeText(resetLink.url);
      copied = true;
    } catch {
      rowErrors = {
        ...rowErrors,
        [rowId]: t('au.copy_failed_link')
      };
    }
  }
</script>

<svelte:head><title>{t('au.head_title')}</title></svelte:head>

<div class="container">
  {#if !allowed || denied}
    <div class="card guard ui">
      <h1>{t('au.guard_h1')}</h1>
      <p>
        {t('au.guard_body')}
        {#if !currentUser.handle}
          {t('au.guard_login')}
        {:else}
          {t('au.guard_no_rights')}
        {/if}
      </p>
      <p><a href="/">{t('common.to_home')}</a></p>
    </div>
  {:else}
    <nav class="ui breadcrumb"><a href="/admin">{t('admin.back_to_hub')}</a></nav>
    <PageHeader title={t('au.h1')} intro={t('au.intro')} />

    <div class="controls ui">
      <div class="filters" role="group" aria-label={t('au.filter_aria')}>
        {#each FILTERS as f (f.value)}
          <button
            type="button"
            class="filter-chip"
            aria-pressed={filter === f.value}
            onclick={() => (filter = f.value)}
          >
            {f.label}
          </button>
        {/each}
      </div>
      <input
        type="search"
        class="row-search"
        placeholder={t('au.search_placeholder')}
        bind:value={q}
        aria-label={t('au.search_aria')}
      />
    </div>

    {#if loadError}
      <p class="error ui" role="alert">{t('au.load_error', { error: loadError })}</p>
    {:else if !loaded}
      <p class="ui muted">{t('au.loading')}</p>
    {:else if rows.length === 0}
      <p class="ui muted">{t('au.no_match')}</p>
    {:else}
      <div class="table-wrap ui">
        <table>
          <thead>
            <tr>
              <th scope="col">{t('au.th_user')}</th>
              <th scope="col">{t('au.th_email')}</th>
              <th scope="col">{t('au.th_org')}</th>
              <th scope="col">{t('common.status')}</th>
              <th scope="col">{t('au.th_created')}</th>
              <th scope="col"><span class="sr-only">{t('au.th_actions_sr')}</span></th>
            </tr>
          </thead>
          <tbody>
            {#each rows as row (row.id)}
              <tr class:inactive={!row.is_active}>
                <td class="who">
                  <span class="name">{row.display_name}</span>
                  <span class="mono handle">{row.handle}</span>
                  {#if row.is_super_admin}
                    <span class="pill st-super">{t('au.badge_super')}</span>
                  {/if}
                  {#if isSelf(row)}
                    <span class="pill st-self">{t('au.badge_self')}</span>
                  {/if}
                </td>
                <td class="email">
                  {#if row.email}<span class="mono">{row.email}</span>{:else}{t('typo.dash')}{/if}
                </td>
                <td class="org">
                  {#if row.memberships.length}
                    {#each row.memberships as membership (membership.id)}
                      <span class="membership-row">
                        {membership.name}
                        <span class="role"
                          >{roleLabel(membership.role)}{membership.kind === 'guest'
                            ? ` · ${t('orgs.kind_guest')}`
                            : ''}</span
                        >
                      </span>
                    {/each}
                  {:else}
                    {t('typo.dash')}
                  {/if}
                </td>
                <td>
                  {#if row.review_status === 'pending'}
                    <span class="status-pending" title={row.review_reason ?? ''}
                      >{t('au.status_pending')}</span
                    >
                  {:else if row.review_status === 'rejected'}
                    <span class="status-inactive">{t('au.status_rejected')}</span>
                  {:else if row.is_active}
                    <span class="status-active">{t('au.status_active')}</span>
                  {:else}
                    <span class="status-inactive">{t('au.status_inactive')}</span>
                  {/if}
                </td>
                <td class="mono created">{formatDate(row.created_at)}</td>
                <td class="actions">
                  {#if !isSelf(row)}
                    {#if row.review_status === 'pending'}
                      <button
                        type="button"
                        class="btn btn-quiet row-action approve"
                        disabled={busyId === row.id}
                        onclick={() => patchRow(row, { review_status: 'approved' })}
                      >
                        {t('au.approve')}
                      </button>
                      <button
                        type="button"
                        class="btn btn-quiet row-action danger"
                        disabled={busyId === row.id}
                        onclick={() => patchRow(row, { review_status: 'rejected' })}
                      >
                        {t('au.reject')}
                      </button>
                    {/if}
                    {#if row.is_active}
                      <button
                        type="button"
                        class="btn btn-quiet row-action danger"
                        disabled={busyId === row.id}
                        onclick={() => (confirming = { id: row.id, action: 'deactivate' })}
                      >
                        {t('au.deactivate')}
                      </button>
                    {:else}
                      <button
                        type="button"
                        class="btn btn-quiet row-action"
                        disabled={busyId === row.id}
                        onclick={() => patchRow(row, { is_active: true })}
                      >
                        {t('au.activate')}
                      </button>
                    {/if}
                    <button
                      type="button"
                      class="btn btn-quiet row-action"
                      disabled={busyId === row.id}
                      onclick={() =>
                        (confirming = { id: row.id, action: row.is_super_admin ? 'revoke' : 'grant' })}
                    >
                      {row.is_super_admin ? t('au.revoke_super') : t('au.grant_super')}
                    </button>
                  {/if}
                  <button
                    type="button"
                    class="btn btn-quiet row-action"
                    disabled={busyId === row.id}
                    onclick={() => makeResetLink(row)}
                    title={t('au.reset_link_title')}
                  >
                    {t('au.create_reset_link')}
                  </button>
                </td>
              </tr>
              {#if rowErrors[row.id]}
                <tr class="detail-row">
                  <td colspan="6"><p class="row-error" role="alert">{rowErrors[row.id]}</p></td>
                </tr>
              {/if}
              {#if confirming?.id === row.id}
                <tr class="detail-row">
                  <td colspan="6">
                    <div class="confirm ui" role="alert">
                      {CONFIRM_TEXTS[confirming.action].question}
                      <button
                        type="button"
                        class="btn btn-quiet"
                        class:danger={confirming.action !== 'grant'}
                        disabled={busyId === row.id}
                        onclick={() => patchRow(row, confirmPayload(confirming!.action))}
                      >
                        {busyId === row.id ? t('common.saving') : CONFIRM_TEXTS[confirming.action].yes}
                      </button>
                      <button
                        type="button"
                        class="btn btn-quiet"
                        disabled={busyId === row.id}
                        onclick={() => (confirming = null)}
                      >
                        {t('common.cancel')}
                      </button>
                    </div>
                  </td>
                </tr>
              {/if}
              {#if resetLinkFor === row.id && resetLink}
                <tr class="detail-row">
                  <td colspan="6">
                    <div class="reset-link card ui">
                      <p class="reset-head">
                        {t('au.reset_head', {
                          name: row.display_name,
                          expires: formatDate(resetLink.expires_at, {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })
                        })}
                      </p>
                      <div class="reset-row">
                        <input
                          type="text"
                          class="input reset-input"
                          readonly
                          value={resetLink.url}
                          aria-label={t('au.reset_link_aria', { name: row.display_name })}
                          onfocus={(e) => e.currentTarget.select()}
                        />
                        <button type="button" class="btn btn-primary" onclick={() => copyLink(row.id)}>
                          {copied ? t('common.copied') : t('common.copy')}
                        </button>
                        <button
                          type="button"
                          class="btn btn-quiet"
                          onclick={() => {
                            resetLinkFor = null;
                            resetLink = null;
                            copied = false;
                          }}
                        >
                          {t('common.close')}
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>

<style>
  .controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
  }

  .filters {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }

  .row-search {
    flex: 1;
    min-width: 220px;
    max-width: 360px;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    color: var(--ink);
  }

  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
    min-width: 960px;
  }

  th {
    text-align: left;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--ink-3);
    padding: var(--space-3);
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
  }

  td {
    padding: var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  tr.inactive > td:not(.actions) {
    opacity: 0.6;
  }

  .who {
    min-width: 200px;
  }

  .name {
    font-weight: 600;
    display: block;
  }

  .handle {
    color: var(--ink-3);
  }

  .st-super {
    margin-left: var(--space-1);
    border-color: var(--endorsed);
    color: var(--endorsed);
  }

  .st-self {
    margin-left: var(--space-1);
    border-color: var(--accent);
    color: var(--accent);
  }

  .org .membership-row {
    display: block;
    white-space: nowrap;
  }

  .org .role {
    display: block;
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .status-active {
    color: var(--ins-strong);
  }

  .status-pending {
    color: var(--accent);
    font-weight: 600;
  }

  .approve {
    color: var(--ins-strong);
  }

  .status-inactive {
    color: var(--del-strong);
  }

  .created {
    white-space: nowrap;
    color: var(--ink-2);
  }

  .actions {
    white-space: nowrap;
  }

  .row-action {
    font-size: var(--text-xs);
  }

  .danger {
    color: var(--del-strong);
  }

  .detail-row td {
    background: var(--bg);
  }

  .row-error {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  .confirm {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .reset-link {
    margin: var(--space-2) 0;
    padding: var(--space-4);
  }

  .reset-head {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-3);
  }

  .reset-row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .reset-input {
    flex: 1;
    min-width: 260px;
    background: var(--bg);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .muted {
    color: var(--ink-3);
  }

  .error {
    padding: var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
  }

</style>
