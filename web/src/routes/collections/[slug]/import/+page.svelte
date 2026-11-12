<script lang="ts">
  import CollectionBadge from '$lib/components/CollectionBadge.svelte';
  import { page } from '$app/state';
  import {
    aiExtractWith,
    api,
    type CollectionOut,
    type ImportResult,
    type ImportRow
  } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { formatNumber, languageLabel, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import { aiSettings, effectiveBaseUrl, effectiveModel } from '$lib/ai/aiKey.svelte';
  import AiSettings from '$lib/ai/AiSettings.svelte';
  import { NO_FEATURES } from '$lib/features';

  // Feature flags from the root layout (FEATURE_AI off ⇒ file import only).
  const features = $derived(page.data.features ?? NO_FEATURES);
  import ColumnHelp from '$lib/import/ColumnHelp.svelte';
  import ImportReport from '$lib/import/ImportReport.svelte';
  import RowPreviewTable from '$lib/import/RowPreviewTable.svelte';
  import { canImport, cleanRows } from '$lib/import/rows';

  const slug = $derived(page.params.slug ?? '');
  const signedIn = $derived(!!currentUser.handle);

  let collection = $state<CollectionOut | null>(null);
  $effect(() => {
    const s = slug;
    api.collection(s).then((c) => (collection = c));
  });

  // ── Tabs ──
  type Tab = 'file' | 'ai';
  let tab = $state<Tab>('file');
  const tabs: { id: Tab; label: string }[] = $derived(
    features.ai
      ? [
          { id: 'file', label: t('imp.tab_file') },
          { id: 'ai', label: t('imp.tab_ai') }
        ]
      : [{ id: 'file', label: t('imp.tab_file') }]
  );

  function onTabKeydown(event: KeyboardEvent): void {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const index = tabs.findIndex((t) => t.id === tab);
    const next = event.key === 'ArrowRight' ? index + 1 : index - 1;
    tab = tabs[(next + tabs.length) % tabs.length].id;
    document.getElementById(`tab-${tab}`)?.focus();
  }

  // ── File import ──
  let file = $state<File | null>(null);
  let fileDry = $state<ImportResult | null>(null);
  let fileDone = $state<ImportResult | null>(null);
  let fileBusy = $state<'dry' | 'import' | null>(null);
  let fileError = $state('');

  function onFileChange(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    file = input.files?.[0] ?? null;
    fileDry = null;
    fileDone = null;
    fileError = '';
  }

  async function runFileImport(dry: boolean): Promise<void> {
    if (!file || fileBusy) return;
    fileBusy = dry ? 'dry' : 'import';
    fileError = '';
    try {
      const result = await api.importFile(slug, file, dry);
      if (dry) {
        fileDry = result;
        fileDone = null;
      } else {
        fileDone = result;
      }
    } catch (err) {
      fileError = errorMessage(err);
    } finally {
      fileBusy = null;
    }
  }

  // ── AI extraction ──
  const MAX_CHARS = 50000;
  let text = $state('');
  let language = $state('');
  let extracting = $state(false);
  let aiError = $state('');
  let rows = $state<ImportRow[]>([]);
  let hasExtracted = $state(false);
  let aiDry = $state<ImportResult | null>(null);
  let aiDone = $state<ImportResult | null>(null);
  let aiBusy = $state<'dry' | 'import' | null>(null);
  let aiImportError = $state('');

  async function extract(): Promise<void> {
    if (extracting || !text.trim() || !aiSettings.key) return;
    extracting = true;
    aiError = '';
    aiDry = null;
    aiDone = null;
    try {
      // model rides in the body (roadmap: body.model always wins);
      // provider + optional base URL become X-LLM-* headers.
      const payload = {
        text,
        ...(language ? { language } : {}),
        model: effectiveModel(aiSettings)
      } as { text: string; language?: string };
      const result = await aiExtractWith(
        payload,
        aiSettings.key,
        aiSettings.provider,
        effectiveBaseUrl(aiSettings)
      );
      rows = result.rows;
      hasExtracted = true;
    } catch (err) {
      aiError = errorMessage(err);
    } finally {
      extracting = false;
    }
  }

  function onRowsEdited(): void {
    aiDry = null;
    aiDone = null;
  }

  async function runRowsImport(dry: boolean): Promise<void> {
    if (aiBusy) return;
    const payload = cleanRows(rows);
    if (payload.length === 0) return;
    aiBusy = dry ? 'dry' : 'import';
    aiImportError = '';
    try {
      const result = await api.importRows(slug, payload, dry);
      if (dry) {
        aiDry = result;
        aiDone = null;
      } else {
        aiDone = result;
      }
    } catch (err) {
      aiImportError = errorMessage(err);
    } finally {
      aiBusy = null;
    }
  }
</script>

<svelte:head>
  <title>{t('imp.head_title', { name: collection?.name ?? t('coll.fallback_title') })}</title>
</svelte:head>

<div class="container">
  <nav class="ui breadcrumb">
    <a href="/collections/{slug}">← {collection?.name ?? t('imp.back_fallback')}</a>
  </nav>

  <header class="head">
    <h1>{t('imp.h1')}</h1>
    <p class="mono meta">
      {t('imp.meta_to')}
      {#if collection}<CollectionBadge {collection} />{:else}{slug}{/if}
      · {collection?.concept_count != null ? formatNumber(collection.concept_count) : '…'} {t('imp.meta_today')}
    </p>
    <p class="desc">
      {t('imp.desc_1')}
      <span class="mono">import</span> {t('imp.desc_2')}
    </p>
  </header>

  {#if !signedIn}
    <div class="card notice ui" role="alert">
      <p>
        <strong>{t('imp.signature_required')}</strong> {t('imp.signature_body')}
      </p>
    </div>
  {/if}

  <div class="ui tabbar" role="tablist" aria-label={t('imp.tablist_aria')}>
    {#each tabs as t (t.id)}
      <button
        class="tabbtn"
        id="tab-{t.id}"
        role="tab"
        aria-selected={tab === t.id}
        aria-controls="panel-{t.id}"
        tabindex={tab === t.id ? 0 : -1}
        class:active={tab === t.id}
        onclick={() => (tab = t.id)}
        onkeydown={onTabKeydown}
      >
        {t.label}
      </button>
    {/each}
  </div>

  <!-- ── CSV / Excel ── -->
  <div
    id="panel-file"
    role="tabpanel"
    aria-labelledby="tab-file"
    class="card panel"
    hidden={tab !== 'file'}
  >
    <div class="ui">
      <p class="step">
        <span class="stepnum mono">1</span>
        {t('imp.step1')}
        <a href={api.importTemplateUrl(slug)} download>{t('imp.template_link')}</a>
      </p>

      <p class="step">
        <span class="stepnum mono">2</span>
        <label class="filelabel">
          {t('imp.choose_file')}
          <input type="file" accept=".csv,.xlsx" onchange={onFileChange} />
        </label>
        {#if file}
          <span class="mono filename">{file.name}</span>
        {/if}
      </p>

      <p class="step actions">
        <span class="stepnum mono">3</span>
        <button
          class="btn btn-primary big"
          disabled={!file || !signedIn || fileBusy !== null}
          aria-busy={fileBusy === 'dry'}
          onclick={() => runFileImport(true)}
        >
          {#if fileBusy === 'dry'}<span class="spinner" aria-hidden="true"></span>{t('imp.validating')}
          {:else}{t('imp.dry_run_btn')}{/if}
        </button>
        <button
          class="btn"
          disabled={!canImport(fileDry) || !signedIn || fileBusy !== null || fileDone !== null}
          aria-busy={fileBusy === 'import'}
          onclick={() => runFileImport(false)}
          title={canImport(fileDry) ? t('imp.import_title_ready') : t('imp.import_title_not_ready')}
        >
          {#if fileBusy === 'import'}<span class="spinner" aria-hidden="true"></span>{t('imp.importing')}
          {:else}{t('imp.import_real')}{/if}
        </button>
      </p>

      {#if fileError}
        <p class="error" role="alert">{fileError}</p>
      {/if}
    </div>

    {#if fileDone}
      <ImportReport result={fileDone} />
      <p class="ui aftermath">
        <a class="btn btn-primary" href="/collections/{slug}">{t('imp.to_collection')}</a>
      </p>
    {:else if fileDry}
      <ImportReport result={fileDry} />
    {/if}
  </div>

  <!-- ── Ostrukturerad text (AI) ── -->
  <div
    id="panel-ai"
    role="tabpanel"
    aria-labelledby="tab-ai"
    class="card panel"
    hidden={!features.ai || tab !== 'ai'}
  >
    <div class="ui">
      <div class="ai-head">
        <p class="ai-intro">
          {t('imp.ai_intro')}
        </p>
        <AiSettings />
      </div>

      {#if !aiSettings.key}
        <p class="hint" role="status">
          {t('imp.need_key')}
        </p>
      {/if}

      <label class="textlabel" for="ai-text">{t('imp.text_label')}</label>
      <textarea
        id="ai-text"
        class="input"
        rows="10"
        maxlength={MAX_CHARS}
        bind:value={text}
        placeholder={t('imp.text_placeholder')}
      ></textarea>
      <p class="mono charcount">{t('imp.charcount', { count: formatNumber(text.length), max: formatNumber(MAX_CHARS) })}</p>

      <p class="actions">
        <label class="langlabel">
          {t('imp.text_lang')}
          <select class="input" bind:value={language} aria-label={t('imp.text_lang')}>
            <option value="">{t('imp.auto_detect')}</option>
            <option value="sv">{languageLabel('sv')}</option>
            <option value="en">{languageLabel('en')}</option>
          </select>
        </label>
        <button
          class="btn btn-primary big"
          disabled={!text.trim() || !aiSettings.key || extracting}
          aria-busy={extracting}
          onclick={extract}
        >
          {#if extracting}<span class="spinner" aria-hidden="true"></span>{t('imp.extracting')}
          {:else}{t('imp.extract')}{/if}
        </button>
      </p>

      {#if aiError}
        <p class="error" role="alert">{aiError}</p>
      {/if}
    </div>

    {#if hasExtracted}
      {#if rows.length === 0}
        <p class="ui hint" role="status">{t('imp.no_rows')}</p>
      {:else}
        <RowPreviewTable {rows} onedit={onRowsEdited} />

        <p class="ui actions">
          <button
            class="btn btn-primary"
            disabled={rows.length === 0 || !signedIn || aiBusy !== null}
            aria-busy={aiBusy === 'dry'}
            onclick={() => runRowsImport(true)}
          >
            {#if aiBusy === 'dry'}<span class="spinner" aria-hidden="true"></span>{t('imp.validating')}
            {:else}{t('imp.dry_run_btn')}{/if}
          </button>
          <button
            class="btn"
            disabled={!canImport(aiDry) || !signedIn || aiBusy !== null || aiDone !== null}
            aria-busy={aiBusy === 'import'}
            onclick={() => runRowsImport(false)}
            title={canImport(aiDry) ? t('imp.import_title_ready') : t('imp.import_title_not_ready')}
          >
            {#if aiBusy === 'import'}<span class="spinner" aria-hidden="true"></span>{t('imp.importing')}
            {:else}{t('imp.import_btn')}{/if}
          </button>
        </p>

        {#if aiImportError}
          <p class="ui error" role="alert">{aiImportError}</p>
        {/if}

        {#if aiDone}
          <ImportReport result={aiDone} />
          <p class="ui aftermath">
            <a class="btn btn-primary" href="/collections/{slug}">{t('imp.to_collection')}</a>
          </p>
        {:else if aiDry}
          <ImportReport result={aiDry} />
        {/if}
      {/if}
    {/if}
  </div>

  <ColumnHelp />
</div>

<style>

  .head h1 {
    margin-bottom: var(--space-2);
  }

  .meta {
    color: var(--ink-3);
    margin-bottom: var(--space-3);
  }

  .desc {
    max-width: 70ch;
    color: var(--ink-2);
  }

  .notice {
    border-color: var(--endorsed);
    margin-bottom: var(--space-6);
    font-size: var(--text-sm);
  }

  .notice p {
    margin: 0;
  }

  /* Tabs */
  .tabbar {
    display: flex;
    gap: var(--space-2);
    border-bottom: 1px solid var(--line);
    margin: var(--space-6) 0 0;
  }

  .tabbtn {
    border: none;
    background: transparent;
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--ink-3);
    padding: var(--space-2) var(--space-4);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    cursor: pointer;
  }

  .tabbtn:hover {
    color: var(--ink);
  }

  .tabbtn.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .panel {
    border-top-left-radius: 0;
    margin-top: 0;
    border-top: none;
  }

  .step {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
    font-size: var(--text-sm);
  }

  .stepnum {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.6em;
    height: 1.6em;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-round);
    flex-shrink: 0;
  }

  .filelabel {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3);
    cursor: pointer;
  }

  .filelabel input {
    font-size: var(--text-sm);
  }

  .filename {
    color: var(--ink-3);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin: var(--space-4) 0 0;
  }

  .big {
    font-size: var(--text-base);
    padding: 0.6em 1.4em;
  }

  .error {
    margin-top: var(--space-3);
    color: var(--del-strong);
    background: var(--del-wash);
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
    font-size: var(--text-sm);
  }

  .hint {
    color: var(--ink-3);
    font-size: var(--text-sm);
    margin: var(--space-3) 0;
  }

  .aftermath {
    margin-top: var(--space-4);
  }

  .aftermath a {
    text-decoration: none;
  }

  /* AI section */
  .ai-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-4);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
  }

  .ai-intro {
    max-width: 62ch;
    color: var(--ink-2);
    font-size: var(--text-sm);
    margin: 0;
  }

  .textlabel {
    display: block;
    font-size: var(--text-sm);
    font-weight: 600;
    margin-bottom: var(--space-1);
  }

  textarea {
    width: 100%;
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .charcount {
    color: var(--ink-3);
    margin: var(--space-1) 0 var(--space-3);
    text-align: right;
  }

  .langlabel {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }

  /* Spinner */
  .spinner {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    margin-right: 0.5em;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: var(--radius-round);
    animation: spin 0.7s linear infinite;
    vertical-align: -0.1em;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
