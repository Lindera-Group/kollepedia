<script lang="ts">
  /** Admin outreach workbench — MANUAL author outreach only.
   * The tool never sends anything: it bookkeeps the admin's own manual
   * workflow and produces copy-ready invitation texts. Opt-out is sacred
   * (enforced server-side; mirrored here). Super admin only. */
  import {
    ApiError,
    listOutreach,
    mintActivationLink,
    patchOutreach,
    type ActivationLinkOut,
    type OutreachRow,
    type OutreachStatus
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import Icon from '$lib/icons/Icon.svelte';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';

  type Filter = 'alla' | 'ej' | 'kontaktade' | 'avbojt' | 'aktiverade';

  let rows = $state<OutreachRow[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let denied = $state(false);

  let filter = $state<Filter>('alla');
  let search = $state('');
  let sortByVersions = $state(false);
  let versionsDesc = $state(true);

  let expandedId = $state<string | null>(null);
  let noteDrafts = $state<Record<string, string>>({});
  let savingId = $state<string | null>(null);
  let rowErrors = $state<Record<string, string>>({});
  let pendingClearId = $state<string | null>(null);
  let copiedId = $state<string | null>(null);
  // Minted personal activation links, per author — baked into the invitation.
  let activationLinks = $state<Record<string, ActivationLinkOut>>({});
  let mintingId = $state<string | null>(null);

  const allowed = $derived(currentUser.is_super_admin);

  async function load(): Promise<void> {
    loading = true;
    loadError = null;
    denied = false;
    try {
      rows = await listOutreach();
      noteDrafts = Object.fromEntries(rows.map((r) => [r.id, r.outreach_note ?? '']));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) denied = true;
      else loadError = errorMessage(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (allowed) load();
  });

  const filterLabels: Record<Filter, string> = $derived({
    alla: t('ao.filter_all'),
    ej: t('ao.filter_not_contacted'),
    kontaktade: t('ao.filter_contacted'),
    avbojt: t('ao.filter_declined'),
    aktiverade: t('ao.filter_activated')
  });

  function matchesFilter(row: OutreachRow, f: Filter): boolean {
    if (f === 'ej') return row.outreach_status === null && !row.activated;
    if (f === 'kontaktade') return row.outreach_status === 'contacted';
    if (f === 'avbojt') return row.outreach_status === 'opted_out';
    if (f === 'aktiverade') return row.activated;
    return true;
  }

  const filterCounts = $derived.by(() => {
    const counts = { alla: rows.length, ej: 0, kontaktade: 0, avbojt: 0, aktiverade: 0 };
    for (const row of rows) {
      for (const f of ['ej', 'kontaktade', 'avbojt', 'aktiverade'] as const) {
        if (matchesFilter(row, f)) counts[f] += 1;
      }
    }
    return counts;
  });

  const visible = $derived.by(() => {
    const needle = search.trim().toLowerCase();
    let out = rows.filter((row) => {
      if (!matchesFilter(row, filter)) return false;
      if (!needle) return true;
      return (
        row.display_name.toLowerCase().includes(needle) ||
        row.handle.toLowerCase().includes(needle) ||
        (row.affiliation ?? '').toLowerCase().includes(needle) ||
        row.collections.some((c) => c.name.toLowerCase().includes(needle))
      );
    });
    if (sortByVersions) {
      out = [...out].sort((a, b) =>
        versionsDesc ? b.version_count - a.version_count : a.version_count - b.version_count
      );
    }
    return out;
  });

  function toggleVersionSort(): void {
    if (sortByVersions) {
      if (versionsDesc) versionsDesc = false;
      else sortByVersions = false; // third click: back to name order
    } else {
      sortByVersions = true;
      versionsDesc = true;
    }
  }

  function statusLabel(status: OutreachStatus): string {
    if (status === 'contacted') return t('ao.status_contacted');
    if (status === 'opted_out') return t('ao.status_declined');
    return t('ao.status_not_contacted');
  }

  async function save(
    row: OutreachRow,
    payload: { status: OutreachStatus; note?: string; confirm_clear_opt_out?: boolean }
  ): Promise<boolean> {
    savingId = row.id;
    const { [row.id]: _removed, ...rest } = rowErrors;
    rowErrors = rest;
    try {
      const updated = await patchOutreach(row.id, payload);
      rows = rows.map((r) => (r.id === row.id ? updated : r));
      noteDrafts = { ...noteDrafts, [row.id]: updated.outreach_note ?? '' };
      return true;
    } catch (e) {
      rowErrors = { ...rowErrors, [row.id]: errorMessage(e) };
      return false;
    } finally {
      savingId = null;
    }
  }

  async function onStatusChange(row: OutreachRow, event: Event): Promise<void> {
    const select = event.currentTarget as HTMLSelectElement;
    const value = (select.value || null) as OutreachStatus;
    if (row.outreach_status === 'opted_out' && value === null) {
      // Clearing an opt-out demands explicit confirmation — never casual.
      pendingClearId = row.id;
      select.value = row.outreach_status ?? '';
      return;
    }
    const ok = await save(row, { status: value });
    if (!ok) select.value = row.outreach_status ?? '';
  }

  async function confirmClear(row: OutreachRow): Promise<void> {
    const ok = await save(row, { status: null, confirm_clear_opt_out: true });
    if (ok) pendingClearId = null;
  }

  function noteDirty(row: OutreachRow): boolean {
    return (noteDrafts[row.id] ?? '') !== (row.outreach_note ?? '');
  }

  async function saveNote(row: OutreachRow): Promise<void> {
    await save(row, { status: row.outreach_status, note: noteDrafts[row.id] ?? '' });
  }

  async function mintLink(row: OutreachRow): Promise<void> {
    mintingId = row.id;
    const { [row.id]: _removed, ...rest } = rowErrors;
    rowErrors = rest;
    try {
      const link = await mintActivationLink(row.id);
      activationLinks = { ...activationLinks, [row.id]: link };
    } catch (e) {
      rowErrors = { ...rowErrors, [row.id]: errorMessage(e) };
    } finally {
      mintingId = null;
    }
  }

  function invitationFor(row: OutreachRow): string {
    const origin = window.location.origin;
    const personal = activationLinks[row.id];
    const activateUrl = `${origin}${personal?.url ?? `/activate?handle=${row.handle}`}`;
    const names = row.collections.map((c) => c.name);
    const collText =
      names.length > 1 ? `${names.slice(0, -1).join(', ')} och ${names.at(-1)}` : (names[0] ?? 'Kollepedia');
    const sections =
      row.section_count > 0
        ? ` och ${row.section_count} ${row.section_count === 1 ? 'definitionssektion' : 'definitionssektioner'}`
        : '';
    const sender = currentUser.display_name || currentUser.handle || 'Kollepedia-redaktionen';
    /* i18n-exempt-start: outreach email is drafted in Swedish on purpose — the
       recipients are the Swedish-speaking authors of the Swedish transit
       terminology, and this is a copy-to-clipboard draft the sender edits by
       hand, not rendered UI. */
    return `Hej ${row.display_name}!

Jag hör av mig eftersom du står som författare till ${row.concept_count} begrepp${sections} i ${collText} – material som nu finns samlat och sökbart på Kollepedia, en öppen begreppsbank för kollektivtrafiken.

Din författarprofil finns här:
${origin}/authors/${row.handle}

Om du vill kan du aktivera ett konto och få redigeringsrätt till dina bidrag – då står du också som ägare till dem framöver:
${activateUrl}${personal ? '\n\nLänken är personlig, gäller i 30 dagar och kan bara användas en gång.' : ''}

Det är förstås helt frivilligt och inget krav – dina bidrag visas med korrekt attribuering oavsett. Och om du inte vill bli kontaktad igen, säg bara till så noterar vi det.

Vänliga hälsningar
${sender}
Kollepedia`;
    /* i18n-exempt-end */
  }

  async function copyInvitation(row: OutreachRow): Promise<void> {
    const { [row.id]: _removed, ...rest } = rowErrors;
    rowErrors = rest;
    try {
      await navigator.clipboard.writeText(invitationFor(row));
      copiedId = row.id;
      setTimeout(() => {
        if (copiedId === row.id) copiedId = null;
      }, 2500);
    } catch {
      rowErrors = {
        ...rowErrors,
        [row.id]: t('ao.copy_failed_text')
      };
    }
  }

  function canInvite(row: OutreachRow): boolean {
    return !row.activated && row.outreach_status !== 'opted_out';
  }

  function inviteTitle(row: OutreachRow): string {
    if (row.activated) return t('ao.invite_activated');
    if (row.outreach_status === 'opted_out') return t('ao.invite_opted_out');
    return t('ao.invite_show');
  }
</script>

<svelte:head><title>{t('ao.head_title')}</title></svelte:head>

<div class="container">
  {#if !allowed || denied}
    <div class="card guard ui">
      <h1>{t('au.guard_h1')}</h1>
      <p>
        {t('ao.guard_body')}
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
    <PageHeader title={t('ao.h1')} />

    <p class="manual-note ui" role="note">
      <strong>{t('ao.manual_note_strong')}</strong>
      {t('ao.manual_note_rest')}
    </p>
    <ol class="workflow ui">
      <li>{t('ao.wf_1a')} <em>{t('ao.filter_not_contacted')}</em></li>
      <li>{t('ao.wf_2a')} <span aria-hidden="true">↗</span>{t('ao.wf_2b')}</li>
      <li>{t('ao.wf_3')}</li>
      <li>{t('ao.wf_4')}</li>
      <li>{t('ao.wf_5')}</li>
    </ol>

    {#if loading}
      <p class="ui muted">{t('authors.loading')}</p>
    {:else if loadError}
      <p class="error ui" role="alert">{t('au.load_error', { error: loadError })}</p>
    {:else}
      <div class="controls ui">
        <div class="filters" role="group" aria-label={t('ao.filter_aria')}>
          {#each Object.entries(filterLabels) as [key, label] (key)}
            <button
              type="button"
              class="filter-chip"
              aria-pressed={filter === key}
              onclick={() => (filter = key as Filter)}
            >
              {label}
              <span class="mono count">{filterCounts[key as Filter]}</span>
            </button>
          {/each}
        </div>
        <input
          type="search"
          class="row-search"
          placeholder={t('ao.search_placeholder')}
          bind:value={search}
          aria-label={t('ao.search_aria')}
        />
      </div>

      {#if visible.length === 0}
        <p class="ui muted">{t('ao.no_match')}</p>
      {:else}
        <div class="table-wrap ui">
          <table>
            <thead>
              <tr>
                <th scope="col">{t('ao.th_author')}</th>
                <th scope="col">{t('ao.th_contrib')}</th>
                <th scope="col">
                  <button
                    type="button"
                    class="sort-btn"
                    onclick={toggleVersionSort}
                    title={t('ao.sort_title')}
                    aria-label="{t('ao.sort_aria_base')}{sortByVersions
                      ? versionsDesc
                        ? t('ao.sort_desc')
                        : t('ao.sort_asc')
                      : ''}"
                  >
                    {t('ao.th_versions')}
                    {#if sortByVersions}<span aria-hidden="true">{versionsDesc ? '▼' : '▲'}</span
                      >{/if}
                  </button>
                </th>
                <th scope="col">{t('common.status')}</th>
                <th scope="col">{t('ao.th_note')}</th>
                <th scope="col"><span class="sr-only">{t('au.th_actions_sr')}</span></th>
              </tr>
            </thead>
            <tbody>
              {#each visible as row (row.id)}
                <tr class:opted-out={row.outreach_status === 'opted_out'}>
                  <td class="who">
                    <a class="name" href="/authors/{row.handle}">{row.display_name}</a>
                    {#if row.activated}<span class="pill st-activated">{t('authors.activated')}</span>{/if}
                    {#if row.affiliation}<span class="affiliation">{row.affiliation}</span>{/if}
                    {#if row.web_url}
                      <a
                        class="ext-link"
                        href={row.web_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={t('ao.ext_title')}
                        aria-label={t('sections.external_profile_aria', { name: row.display_name })}
                        >↗</a
                      >
                    {/if}
                  </td>
                  <td class="contrib">
                    <span class="mono counts"
                      >{row.concept_count} {t('common.concepts')}{#if row.section_count > 0}
                        · {row.section_count} {t('ao.sections_abbrev')}{/if}</span
                    >
                    <span class="pills">
                      {#each row.collections as coll (coll.slug)}
                        <span class="pill">{coll.name}</span>
                      {/each}
                    </span>
                  </td>
                  <td class="mono versions">{row.version_count}</td>
                  <td class="status">
                    <select
                      class="input input-compact"
                      value={row.outreach_status ?? ''}
                      onchange={(e) => onStatusChange(row, e)}
                      disabled={savingId === row.id}
                      aria-label={t('ao.status_aria', { name: row.display_name })}
                    >
                      <option value="">{statusLabel(null)}</option>
                      <option value="contacted" disabled={row.outreach_status === 'opted_out'}>
                        {statusLabel('contacted')}
                      </option>
                      <option value="opted_out">{statusLabel('opted_out')}</option>
                    </select>
                    {#if row.outreach_updated_at}
                      <span class="updated mono">{formatDate(row.outreach_updated_at)}</span>
                    {/if}
                    {#if pendingClearId === row.id}
                      <span class="clear-confirm" role="alert">
                        {t('ao.clear_confirm')}
                        <button
                          type="button"
                          class="btn btn-quiet danger clear-btn"
                          disabled={savingId === row.id}
                          onclick={() => confirmClear(row)}>{t('ao.clear_yes')}</button
                        >
                        <button
                          type="button"
                          class="btn btn-quiet clear-btn"
                          onclick={() => (pendingClearId = null)}>{t('common.cancel')}</button
                        >
                      </span>
                    {/if}
                  </td>
                  <td class="note">
                    <input
                      type="text"
                      class="input input-compact note-input"
                      value={noteDrafts[row.id] ?? ''}
                      oninput={(e) =>
                        (noteDrafts = {
                          ...noteDrafts,
                          [row.id]: (e.currentTarget as HTMLInputElement).value
                        })}
                      placeholder={t('ao.note_placeholder')}
                      aria-label={t('ao.note_aria', { name: row.display_name })}
                    />
                    {#if noteDirty(row)}
                      <button
                        type="button"
                        class="btn btn-quiet note-save"
                        disabled={savingId === row.id}
                        onclick={() => saveNote(row)}
                      >
                        {savingId === row.id ? t('common.saving') : t('common.save')}
                      </button>
                    {/if}
                  </td>
                  <td class="actions">
                    <button
                      type="button"
                      class="btn"
                      disabled={!canInvite(row)}
                      title={inviteTitle(row)}
                      aria-expanded={expandedId === row.id}
                      onclick={() => (expandedId = expandedId === row.id ? null : row.id)}
                    >
                      {t('ao.invite')}
                    </button>
                  </td>
                </tr>
                {#if rowErrors[row.id]}
                  <tr class="error-row">
                    <td colspan="6"><p class="row-error" role="alert">{rowErrors[row.id]}</p></td>
                  </tr>
                {/if}
                {#if expandedId === row.id && canInvite(row)}
                  <tr class="invite-row">
                    <td colspan="6">
                      <div class="invite card">
                        <p class="invite-head">
                          {t('ao.invite_head', { name: row.display_name })}
                          <strong>{t('ao.never_auto')}</strong>
                        </p>
                        <div class="mint">
                          {#if activationLinks[row.id]}
                            <p class="mint-done" role="status">
                              <Icon name="check" size={14} />
                              {t('ao.mint_done', {
                                date: formatDate(activationLinks[row.id].expires_at)
                              })}
                            </p>
                          {:else}
                            <button
                              type="button"
                              class="btn"
                              disabled={mintingId === row.id}
                              onclick={() => mintLink(row)}
                            >
                              {mintingId === row.id ? t('ao.minting') : t('ao.mint_link')}
                            </button>
                            <p class="mint-hint">{t('ao.mint_hint')}</p>
                          {/if}
                        </div>
                        <textarea readonly rows="14" class="input invite-textarea" value={invitationFor(row)}
                          aria-label={t('ao.invite_text_aria', { name: row.display_name })}></textarea>
                        <div class="invite-actions">
                          <button type="button" class="btn btn-primary" onclick={() => copyInvitation(row)}>
                            {copiedId === row.id ? t('common.copied') : t('common.copy')}
                          </button>
                          <button
                            type="button"
                            class="btn"
                            disabled={savingId === row.id || row.outreach_status === 'contacted'}
                            onclick={() => save(row, { status: 'contacted' })}
                          >
                            {row.outreach_status === 'contacted'
                              ? t('ao.marked_contacted')
                              : t('ao.mark_contacted')}
                          </button>
                          <button type="button" class="btn btn-quiet" onclick={() => (expandedId = null)}>
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
  {/if}
</div>

<style>
  .manual-note {
    max-width: 68ch;
    margin: 0 0 var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent-soft);
    font-size: var(--text-sm);
  }

  .workflow {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    margin: 0 0 var(--space-6);
    padding-left: var(--space-4);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

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

  .filters .count {
    opacity: 0.7;
    margin-left: 0.3em;
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
    min-width: 920px;
  }

  th {
    text-align: left;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--ink-3);
    padding: var(--space-3) var(--space-3);
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
  }

  .sort-btn {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: inherit;
    text-transform: inherit;
    letter-spacing: inherit;
    cursor: pointer;
  }

  .sort-btn:hover {
    color: var(--ink);
  }

  td {
    padding: var(--space-3) var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  tr.opted-out td {
    opacity: 0.75;
  }

  .who {
    min-width: 230px;
  }

  .name {
    font-weight: 600;
    color: var(--ink);
    text-decoration: none;
  }

  .name:hover {
    color: var(--accent);
  }

  .st-activated {
    margin-left: var(--space-1);
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .affiliation {
    display: block;
    font-size: var(--text-xs);
    color: var(--ink-3);
    max-width: 34ch;
  }

  .ext-link {
    margin-left: var(--space-1);
    color: var(--accent);
    text-decoration: none;
  }

  .contrib {
    min-width: 200px;
  }

  .counts {
    display: block;
    font-size: var(--text-xs);
    color: var(--ink-2);
    margin-bottom: var(--space-1);
  }

  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .versions {
    text-align: left;
    color: var(--ink-2);
  }

  /* Compact table-cell flavour of the .input primitive. */
  .input-compact {
    padding: 0.3em 0.6em;
    background: var(--bg);
    font-size: var(--text-xs);
  }

  .updated {
    display: block;
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin-top: var(--space-1);
  }

  .clear-confirm {
    display: block;
    margin-top: var(--space-2);
    font-size: var(--text-xs);
    color: var(--ink-2);
    max-width: 26ch;
  }

  .clear-btn {
    margin-top: var(--space-1);
  }

  .danger {
    color: var(--del-strong);
  }

  .note-input {
    width: 100%;
    min-width: 160px;
  }

  .note-save {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
  }

  .actions {
    white-space: nowrap;
  }

  .error-row td,
  .invite-row td {
    border-bottom: 1px solid var(--line);
    background: var(--bg);
  }

  .row-error {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--del-strong);
  }

  .invite {
    margin: var(--space-2) 0;
  }

  .invite-head {
    font-size: var(--text-sm);
    color: var(--ink-2);
    margin: 0 0 var(--space-3);
  }

  .mint {
    margin: 0 0 var(--space-3);
  }

  .mint-done {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin: 0;
  }

  .mint-hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: var(--space-1) 0 0;
    max-width: 68ch;
    line-height: 1.5;
  }

  .invite-textarea {
    width: 100%;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    line-height: 1.6;
    padding: var(--space-3);
    background: var(--bg);
  }

  .invite-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
    flex-wrap: wrap;
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
