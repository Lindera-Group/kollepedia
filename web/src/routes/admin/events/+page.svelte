<script lang="ts">
  /** Superadmin audit log (guardrail G5): every super-admin action —
   * approve/suspend orgs, suspend/restore users, ownership transfers —
   * lands in admin_events, append-only. The guard mirrors /admin/users. */
  import { adminEvents, ApiError, type AdminEventOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  let rows = $state<AdminEventOut[]>([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let denied = $state(false);

  const allowed = $derived(currentUser.is_super_admin);

  $effect(() => {
    if (!allowed) return;
    adminEvents(200)
      .then((result) => {
        rows = result;
        loaded = true;
      })
      .catch((e) => {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) denied = true;
        else loadError = errorMessage(e);
      });
  });

  function actionLabel(action: string): string {
    switch (action) {
      case 'org_created':
        return t('adminev.action_org_created');
      case 'org_approved':
        return t('adminev.action_org_approved');
      case 'org_suspended':
        return t('adminev.action_org_suspended');
      case 'org_unsuspended':
        return t('adminev.action_org_unsuspended');
      case 'org_owner_transferred':
        return t('adminev.action_owner_transferred');
      case 'user_suspended':
        return t('adminev.action_user_suspended');
      case 'user_restored':
        return t('adminev.action_user_restored');
      case 'superadmin_granted':
        return t('adminev.action_superadmin_granted');
      case 'superadmin_revoked':
        return t('adminev.action_superadmin_revoked');
      default:
        return action;
    }
  }
</script>

<svelte:head><title>{t('adminev.head_title')}</title></svelte:head>

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
    <PageHeader title={t('adminev.h1')} intro={t('adminev.intro')} />

    {#if loadError}
      <p class="error ui" role="alert">{t('adminev.load_error', { error: loadError })}</p>
    {:else if !loaded}
      <p class="ui muted">{t('adminev.loading')}</p>
    {:else if rows.length === 0}
      <p class="ui muted">{t('adminev.empty')}</p>
    {:else}
      <div class="table-wrap ui">
        <table>
          <thead>
            <tr>
              <th scope="col">{t('adminev.th_when')}</th>
              <th scope="col">{t('adminev.th_actor')}</th>
              <th scope="col">{t('adminev.th_action')}</th>
              <th scope="col">{t('adminev.th_target')}</th>
              <th scope="col">{t('adminev.th_note')}</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as row (row.id)}
              <tr>
                <td class="mono when">{formatDate(row.created_at)}</td>
                <td class="mono">{row.actor_handle ?? row.actor_id}</td>
                <td>{actionLabel(row.action)}</td>
                <td class="mono target">{row.target_type}</td>
                <td class="note-cell">{row.note ?? t('typo.dash')}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>

<style>
  .muted {
    color: var(--ink-3);
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
  }

  .table-wrap {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  th {
    text-align: left;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
    padding: var(--space-2);
    border-bottom: 1px solid var(--line);
  }

  td {
    padding: var(--space-2);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  .when,
  .target {
    white-space: nowrap;
    color: var(--ink-3);
    font-size: var(--text-xs);
  }

  .note-cell {
    max-width: 40ch;
    overflow-wrap: anywhere;
  }
</style>
