<script lang="ts">
  /** Admin email outbox (iteration 4). Super admin only — the guard mirrors
   * /admin/users. Every email the system generates lands here; a hard
   * allowlist in the backend guarantees nothing leaves to other addresses
   * (non-allowlisted recipients are stored with status 'blocked'). */
  import { ApiError, night4, type OutboxMessage } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  let rows = $state<OutboxMessage[]>([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let denied = $state(false);
  let expanded = $state<Record<string, boolean>>({});

  const allowed = $derived(currentUser.is_super_admin);

  $effect(() => {
    if (!allowed) return;
    night4
      .outbox(100)
      .then((result) => {
        rows = result;
        loaded = true;
      })
      .catch((e) => {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) denied = true;
        else loadError = errorMessage(e);
      });
  });

  function statusLabelFor(status: OutboxMessage['status']): string {
    switch (status) {
      case 'queued':
        return t('profile.outbox_status_queued');
      case 'sent':
        return t('profile.outbox_status_sent');
      case 'blocked':
        return t('profile.outbox_status_blocked');
      default:
        return t('profile.outbox_status_outbox');
    }
  }

  function toggle(id: string): void {
    expanded = { ...expanded, [id]: !expanded[id] };
  }
</script>

<svelte:head><title>{t('profile.outbox_head_title')}</title></svelte:head>

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
    <PageHeader title={t('profile.outbox_h1')} intro={t('profile.outbox_intro')} />

    <p class="allowlist-note ui" role="note">
      <strong>{t('profile.outbox_note')}</strong>
    </p>

    {#if loadError}
      <p class="error ui" role="alert">{t('profile.outbox_load_error', { error: loadError })}</p>
    {:else if !loaded}
      <p class="ui muted">{t('profile.outbox_loading')}</p>
    {:else if rows.length === 0}
      <p class="ui muted">{t('profile.outbox_empty')}</p>
    {:else}
      <div class="table-wrap ui">
        <table>
          <thead>
            <tr>
              <th scope="col">{t('profile.outbox_th_to')}</th>
              <th scope="col">{t('profile.outbox_th_subject')}</th>
              <th scope="col">{t('common.status')}</th>
              <th scope="col">{t('profile.outbox_th_date')}</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as row (row.id)}
              <tr>
                <td class="mono to">{row.to_addr}</td>
                <td class="subject">
                  <button
                    type="button"
                    class="subject-btn"
                    aria-expanded={!!expanded[row.id]}
                    onclick={() => toggle(row.id)}
                    title={t('profile.outbox_show_body')}
                  >
                    <span class="caret" aria-hidden="true">{expanded[row.id] ? '▾' : '▸'}</span>
                    {row.subject}
                  </button>
                  <span class="mono template">{row.template}</span>
                </td>
                <td>
                  <span class="pill st-{row.status}">{statusLabelFor(row.status)}</span>
                </td>
                <td class="mono created">
                  {formatDate(row.created_at, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </td>
              </tr>
              {#if expanded[row.id]}
                <tr class="body-row">
                  <td colspan="4">
                    <pre class="mail-body">{row.body_text}</pre>
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
  .allowlist-note {
    max-width: 68ch;
    margin: 0 0 var(--space-6);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--endorsed);
    border-left-width: 3px;
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
    color: var(--ink-2);
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
    min-width: 720px;
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

  .to {
    white-space: nowrap;
  }

  .subject-btn {
    display: inline-flex;
    align-items: baseline;
    gap: var(--space-1);
    border: none;
    background: none;
    padding: 0;
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--ink);
    text-align: left;
    cursor: pointer;
  }

  .subject-btn:hover {
    color: var(--accent);
  }

  .caret {
    font-size: 0.8em;
    color: var(--ink-3);
  }

  .template {
    display: block;
    margin-top: 2px;
    color: var(--ink-3);
  }

  .st-sent {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .st-blocked {
    border-color: var(--del-strong);
    color: var(--del-strong);
    background: var(--del-wash);
  }

  .st-queued {
    border-style: dashed;
  }

  .created {
    white-space: nowrap;
    color: var(--ink-2);
  }

  .body-row td {
    background: var(--bg);
  }

  .mail-body {
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-sunken);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
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
