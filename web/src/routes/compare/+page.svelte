<script lang="ts">
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import CollectionBadge from '$lib/components/CollectionBadge.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { untrack } from 'svelte';
  import {
    aiDraftWith,
    api,
    ApiError,
    night4,
    type AiDraftOut,
    type AiDraftPayload,
    type ConceptListItem,
    type ConceptOut,
    type SavedPromptOut,
    type VersionOut
  } from '$lib/api';
  import AiSettings from '$lib/ai/AiSettings.svelte';
  import { aiSettings, effectiveBaseUrl, effectiveModel } from '$lib/ai/aiKey.svelte';
  import { errorMessage } from '$lib/errors';
  import HelpTip from '$lib/help/HelpTip.svelte';
  import { buildDiffSegments } from '$lib/compare/diffSegments';
  import { compareUrl, parseIds, withId, withoutId } from '$lib/compare/url';
  import { formatDate, languageLabel, statusLabel, t } from '$lib/i18n.svelte';
  import { shortId } from '$lib/lists/pin';
  import { renderMarkdown, stripMarkdown } from '$lib/text';
  import { currentUser } from '$lib/user.svelte';
  import { NO_FEATURES } from '$lib/features';

  // Feature flags from the root layout (FEATURE_AI off ⇒ no AI UI at all).
  const features = $derived(page.data.features ?? NO_FEATURES);

  type Col =
    | { status: 'loading' }
    | { status: 'error'; message: string }
    | { status: 'ok'; concept: ConceptOut };

  const ids = $derived(parseIds(page.url.searchParams.get('ids')));

  let cols = $state<Record<string, Col>>({});

  $effect(() => {
    const wanted = ids;
    untrack(() => {
      for (const conceptId of wanted) {
        if (cols[conceptId]) continue;
        cols[conceptId] = { status: 'loading' };
        api
          .concept(conceptId)
          .then((concept) => {
            cols[conceptId] = { status: 'ok', concept };
          })
          .catch((e) => {
            cols[conceptId] = {
              status: 'error',
              message: errorMessage(e)
            };
          });
      }
    });
  });

  // ── Base column ("utgångspunkt") ──
  let baseChoice = $state<string | null>(null);
  const baseId = $derived(
    baseChoice && ids.includes(baseChoice) ? baseChoice : (ids[0] ?? null)
  );
  const baseHead = $derived.by((): VersionOut | null => {
    if (!baseId) return null;
    const col = cols[baseId];
    return col?.status === 'ok' ? col.concept.head : null;
  });
  const baseDefPlain = $derived(baseHead ? stripMarkdown(baseHead.definition_md) : '');

  // ── Diff mode ──
  let diffMode = $state(false);

  // Columns that loaded and have a head — the harmonisable material.
  const loaded = $derived.by(() => {
    const out: { conceptId: string; concept: ConceptOut; head: VersionOut }[] = [];
    for (const conceptId of ids) {
      const col = cols[conceptId];
      if (col?.status === 'ok' && col.concept.head) {
        out.push({ conceptId, concept: col.concept, head: col.concept.head });
      }
    }
    return out;
  });

  function navigate(nextIds: string[]): void {
    void goto(compareUrl(nextIds), { replaceState: true, keepFocus: true, noScroll: true });
  }

  function removeConcept(conceptId: string): void {
    if (baseChoice === conceptId) baseChoice = null;
    navigate(withoutId(ids, conceptId));
  }

  // ── Add-concept search ──
  let addQ = $state('');
  let addResults = $state<ConceptListItem[]>([]);
  let addSearching = $state(false);
  let addTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const query = addQ.trim();
    clearTimeout(addTimer);
    if (!query) {
      addResults = [];
      addSearching = false;
      return;
    }
    addSearching = true;
    addTimer = setTimeout(() => {
      api
        .concepts({ q: query, limit: 8 })
        .then((r) => {
          addResults = r.items.filter((item) => !ids.includes(item.id));
          addSearching = false;
        })
        .catch(() => {
          addSearching = false;
        });
    }, 220);
  });

  function addConcept(conceptId: string): void {
    navigate(withId(ids, conceptId));
    addQ = '';
    addResults = [];
  }

  function onSearchKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && addQ) {
      event.preventDefault();
      addQ = '';
      addResults = [];
    }
  }

  // ── Harmonisera (BYOK AI synthesis, VISION §5 + §6) ──
  let panelOpen = $state(false);
  let guidance = $state('');
  let drafting = $state(false);
  let draftError = $state<string | null>(null);
  let draftMeta = $state<AiDraftOut | null>(null);
  let formCanonical = $state('');
  let formDefinition = $state('');
  let formNote = $state('');
  let savingSynth = $state(false);
  let synthError = $state<string | null>(null);
  let savedConceptId = $state<string | null>(null);

  interface PanelParents {
    baseConceptId: string;
    baseForm: string;
    baseHeadId: string;
    otherHeadIds: string[];
  }
  let parents = $state<PanelParents | null>(null);

  const canHarmonise = $derived(loaded.length >= 2 && !!aiSettings.key);
  const harmoniseHint = $derived(
    loaded.length < 2
      ? t('cmp.harmonise_hint_two')
      : !aiSettings.key
        ? t('aiprov.hint_key')
        : t('cmp.harmonise_hint_ready')
  );

  // ── Saved prompts (iteration 4 — guidance presets, intent 'synthesize') ──
  let prompts = $state<SavedPromptOut[]>([]);
  let selectedPromptId = $state('');
  let presetFormOpen = $state(false);
  let presetName = $state('');
  let presetShared = $state(false);
  let presetBusy = $state(false);
  let presetError = $state<string | null>(null);
  let presetSaved = $state(false);

  function loadPrompts(): void {
    night4
      .prompts('synthesize')
      .then((list) => (prompts = list))
      .catch(() => {
        /* prompts are progressive enhancement — the select simply stays empty */
      });
  }

  function onPresetChange(): void {
    const preset = prompts.find((p) => p.id === selectedPromptId);
    if (preset) guidance = preset.text;
  }

  function onGuidanceInput(): void {
    // Manual edits detach the guidance from the preset (prompt_id no longer true).
    const preset = prompts.find((p) => p.id === selectedPromptId);
    if (preset && guidance !== preset.text) selectedPromptId = '';
  }

  async function savePreset(): Promise<void> {
    presetError = null;
    presetSaved = false;
    if (!presetName.trim()) {
      presetError = t('aiprov.preset_error_no_name');
      return;
    }
    if (!guidance.trim()) {
      presetError = t('aiprov.preset_error_no_text');
      return;
    }
    presetBusy = true;
    try {
      const created = await night4.createPrompt({
        name: presetName.trim(),
        intent: 'synthesize',
        text: guidance.trim(),
        shared: presetShared
      });
      prompts = [...prompts, created];
      selectedPromptId = created.id;
      presetFormOpen = false;
      presetName = '';
      presetShared = false;
      presetSaved = true;
    } catch (e) {
      presetError = t('aiprov.preset_save_failed', {
        error: errorMessage(e)
      });
    } finally {
      presetBusy = false;
    }
  }

  function openPanel(): void {
    panelOpen = true;
    synthError = null;
    savedConceptId = null;
    if (features.ai) loadPrompts();
  }

  function closePanel(): void {
    panelOpen = false;
  }

  async function requestDraft(): Promise<void> {
    const base = loaded.find((entry) => entry.conceptId === baseId) ?? loaded[0];
    if (!base || loaded.length < 2 || !aiSettings.key) return;
    const others = loaded.filter((entry) => entry.conceptId !== base.conceptId);
    parents = {
      baseConceptId: base.conceptId,
      baseForm: base.head.canonical_form,
      baseHeadId: base.head.id,
      otherHeadIds: others.map((entry) => entry.head.id)
    };
    drafting = true;
    draftError = null;
    savedConceptId = null;
    try {
      // prompt_id rides along in provenance when a saved preset is used.
      const payload = {
        intent: 'synthesize',
        version_ids: [base.head.id, ...others.map((entry) => entry.head.id)],
        guidance: guidance.trim() || undefined,
        model: effectiveModel(aiSettings),
        ...(selectedPromptId ? { prompt_id: selectedPromptId } : {})
      } as AiDraftPayload;
      const draft = await aiDraftWith(
        payload,
        aiSettings.key,
        aiSettings.provider,
        effectiveBaseUrl(aiSettings)
      );
      draftMeta = draft;
      formCanonical = draft.canonical_form;
      formDefinition = draft.definition_md;
      formNote = draft.note_suggestion;
    } catch (e) {
      draftError =
        e instanceof ApiError
          ? `${e.status === 502 ? t('cmp.ai_provider_error') : t('cmp.draft_failed')}: ${errorMessage(e)}`
          : errorMessage(e);
    } finally {
      drafting = false;
    }
  }

  const canSaveSynthesis = $derived(
    !!parents &&
      !!draftMeta &&
      !savingSynth &&
      !!currentUser.handle &&
      formCanonical.trim().length > 0 &&
      formDefinition.trim().length > 0
  );

  async function saveSynthesis(): Promise<void> {
    if (!parents || !canSaveSynthesis) return;
    savingSynth = true;
    synthError = null;
    try {
      await api.createVersion(parents.baseConceptId, {
        mode: 'synthesize',
        base_version_id: parents.baseHeadId,
        extra_parent_ids: parents.otherHeadIds,
        canonical_form: formCanonical.trim(),
        definition_md: formDefinition,
        note: formNote.trim() || undefined,
        status: 'draft'
      });
      savedConceptId = parents.baseConceptId;
    } catch (e) {
      synthError = errorMessage(e);
    } finally {
      savingSynth = false;
    }
  }
</script>

<svelte:head><title>{t('cmp.head_title')}</title></svelte:head>

<div class="container">
  <PageHeader title={t('cmp.h1')} intro={t('cmp.tagline')} />

  <div class="toolbar ui">
    <label class="diff-toggle" class:on={diffMode}>
      <input type="checkbox" bind:checked={diffMode} disabled={!baseHead || ids.length < 2} />
      {t('cmp.diff_mode')}
    </label>
    <HelpTip topic="compare-base" />

    <div class="add" role="search">
      <input
        type="search"
        class="input"
        bind:value={addQ}
        onkeydown={onSearchKeydown}
        placeholder={t('cmp.add_placeholder')}
        aria-label={t('cmp.add_aria')}
      />
      {#if addQ.trim()}
        <div class="add-results card">
          {#if addSearching}
            <p class="muted"><span class="spinner" aria-hidden="true"></span> {t('common.searching')}</p>
          {:else if addResults.length === 0}
            <p class="muted">{t('combo.no_hits')}</p>
          {:else}
            {#each addResults as result (result.id)}
              <button class="add-hit" onclick={() => addConcept(result.id)}>
                <span class="hit-form">{result.canonical_form}</span>
                <span class="mono hit-coll">
                  {result.collection_name}{result.collection_year ? ` · ${result.collection_year}` : ''}
                </span>
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </div>

    <span class="spacer"></span>

    {#if features.ai}
    <span title={harmoniseHint}>
      <button
        class="btn harmonise-btn"
        class:btn-primary={canHarmonise}
        onclick={openPanel}
        disabled={!canHarmonise}
        aria-label={t('cmp.harmonise_aria', { hint: harmoniseHint })}
      >
        <Icon name="sparkle" size={14} /> {t('cmp.harmonise')}
      </button>
    </span>
    <AiSettings />
    {/if}
  </div>

  {#if panelOpen}
    <section class="harmonise card" aria-label={t('cmp.panel_aria')}>
      <div class="panel-head ui">
        <h2>{t('cmp.harmonise')}</h2>
        <button class="btn btn-quiet" onclick={closePanel} aria-label={t('cmp.close_panel_aria')}>×</button>
      </div>

      <p class="panel-sub ui">
        {t('cmp.panel_sub_1', { count: loaded.length })}
        <strong>”{(loaded.find((entry) => entry.conceptId === baseId) ?? loaded[0])?.head
          .canonical_form}”</strong>
        {t('cmp.panel_sub_2')}
      </p>

      {#if prompts.length > 0}
        <label class="field ui preset-pick">
          <span>{t('aiprov.preset_label')} <span class="muted">{t('common.optional_paren')}</span></span>
          <select class="input" bind:value={selectedPromptId} onchange={onPresetChange}>
            <option value="">{t('aiprov.preset_none')}</option>
            {#each prompts as preset (preset.id)}
              <option value={preset.id}>
                {preset.name}{preset.shared ? ` ${t('typo.dash')} ${t('aiprov.preset_shared_suffix')}` : ''}
              </option>
            {/each}
          </select>
        </label>
      {/if}

      <label class="field ui">
        <span>{t('cmp.guidance_label')} <span class="muted">{t('common.optional_paren')}</span></span>
        <textarea
          rows="2"
          class="input"
          bind:value={guidance}
          oninput={onGuidanceInput}
          placeholder={t('cmp.guidance_placeholder')}
        ></textarea>
      </label>

      <div class="preset-save ui">
        {#if presetFormOpen}
          <div class="preset-form" role="group" aria-label={t('aiprov.save_as_preset')}>
            <label class="field preset-name">
              <span>{t('aiprov.preset_name_label')}</span>
              <input
                type="text"
                class="input"
                bind:value={presetName}
                placeholder={t('aiprov.preset_name_placeholder')}
              />
            </label>
            <label class="preset-shared">
              <input type="checkbox" bind:checked={presetShared} />
              {t('aiprov.preset_shared_label')}
            </label>
            <div class="row">
              <button class="btn" onclick={() => void savePreset()} disabled={presetBusy}>
                {presetBusy ? t('aiprov.preset_saving') : t('aiprov.preset_save')}
              </button>
              <button class="btn btn-quiet" onclick={() => (presetFormOpen = false)}>
                {t('common.cancel')}
              </button>
            </div>
          </div>
        {:else}
          <button
            class="btn btn-quiet preset-open"
            onclick={() => {
              presetFormOpen = true;
              presetSaved = false;
            }}
            disabled={!guidance.trim()}
          >
            {t('aiprov.save_as_preset')}
          </button>
        {/if}
        {#if presetError}
          <p class="error" role="alert">{presetError}</p>
        {/if}
        {#if presetSaved}
          <p class="saved-inline" role="status"><Icon name="check" size={14} /> {t('aiprov.preset_saved')}</p>
        {/if}
      </div>

      <div class="row ui">
        <button class="btn btn-primary" onclick={() => void requestDraft()} disabled={drafting || !canHarmonise}>
          {#if drafting}<span class="spinner" aria-hidden="true"></span>
            {t('cmp.creating_draft')}{:else if draftMeta}{t('cmp.new_draft')}{:else}{t('cmp.create_draft')}{/if}
        </button>
      </div>

      {#if draftError}
        <p class="error ui" role="alert">{draftError}</p>
      {/if}

      {#if draftMeta}
        <div class="review ui">
          <p class="prov mono">{t('cmp.ai_draft')} · {draftMeta.model}</p>

          <label class="field">
            <span>{t('cmp.term_label')}</span>
            <input type="text" class="input" bind:value={formCanonical} />
          </label>

          <label class="field">
            <span>{t('cmp.definition_label')}</span>
            <textarea rows="8" class="input" bind:value={formDefinition}></textarea>
          </label>

          <label class="field">
            <span>{t('cmp.note_label')} <span class="muted">{t('cmp.note_hint')}</span></span>
            <textarea rows="2" class="input" bind:value={formNote}></textarea>
          </label>

          {#if synthError}
            <p class="error" role="alert">{synthError}</p>
          {/if}

          {#if savedConceptId}
            <p class="saved" role="status">
              <Icon name="check" size={14} /> {t('cmp.synth_saved_1')} <strong>{parents?.baseForm}</strong>.
              <a href="/concepts/{savedConceptId}/history">{t('cmp.open_tm')}</a>
            </p>
          {:else}
            <div class="row">
              <button class="btn btn-primary" onclick={() => void saveSynthesis()} disabled={!canSaveSynthesis}>
                {#if savingSynth}<span class="spinner" aria-hidden="true"></span>
                  {t('common.saving')}{:else}{t('cmp.save_synth', { form: parents?.baseForm ?? '' })}{/if}
              </button>
              {#if !currentUser.handle}
                <span class="muted hint">{t('cmp.sign_to_save')}</span>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </section>
  {/if}

  {#if ids.length === 0}
    <div class="card state-card ui">
      <p>
        {t('cmp.empty_1')}
        <a href="/lists">{t('cmp.empty_link')}</a> {t('cmp.empty_2')} <strong>{t('cmp.empty_cta')}</strong>.
      </p>
    </div>
  {:else}
    {#if diffMode && baseHead}
      <p class="legend mono ui">
        <span class="s del">{t('cmp.legend_del')}</span>
        <span class="s ins">{t('cmp.legend_ins')}</span>
      </p>
    {/if}

    <div class="workbench full-bleed" role="region" aria-label={t('cmp.workbench_aria')}>
      <div class="cols">
        {#each ids as conceptId (conceptId)}
          {@const col = cols[conceptId]}
          <section
            class="col"
            class:is-base={conceptId === baseId}
            aria-label={col?.status === 'ok' && col.concept.head
              ? col.concept.head.canonical_form
              : t('cmp.concept_fallback')}
          >
            {#if col?.status === 'ok' && col.concept.head}
              {@const head = col.concept.head}
              <header class="col-head">
                <div class="col-top ui">
                  <label class="base-pick mono" title={t('cmp.base_pick_title')}>
                    <input
                      type="radio"
                      name="compare-base"
                      value={conceptId}
                      checked={conceptId === baseId}
                      onchange={() => (baseChoice = conceptId)}
                    />
                    {t('cmp.base')}
                  </label>
                  <button
                    class="btn btn-quiet remove"
                    onclick={() => removeConcept(conceptId)}
                    aria-label={t('cmp.remove_aria', { name: head.canonical_form })}
                  >
                    ×
                  </button>
                </div>
                <h2><a href="/concepts/{conceptId}">{head.canonical_form}</a></h2>
                <div class="coll">
                  <CollectionBadge collection={col.concept.collection} />
                </div>
                <div class="pills ui">
                  <span class="pill pill-status-{head.status}">
                    {statusLabel(head.status)}
                  </span>
                  <span class="pill">{languageLabel(head.language)}</span>
                  {#each head.tags as tag (tag)}
                    <span class="pill">{tag}</span>
                  {/each}
                </div>
              </header>

              <div class="col-body">
                {#if diffMode && baseHead && conceptId !== baseId}
                  <p class="def plain">
                    {#each buildDiffSegments(baseDefPlain, stripMarkdown(head.definition_md)) as segment, i (i)}
                      <span class="s {segment.type}">{segment.text}</span>
                    {/each}
                  </p>
                {:else if diffMode && conceptId === baseId}
                  <p class="def plain">{stripMarkdown(head.definition_md)}</p>
                {:else}
                  <div class="def">
                    <!-- eslint-disable-next-line svelte/no-at-html-tags — renderMarkdown escapes first -->
                    {@html renderMarkdown(head.definition_md)}
                  </div>
                {/if}

                <footer class="col-foot ui">
                  <p>
                    <AuthorLink user={head.created_by} />
                    · {formatDate(head.created_at)}
                  </p>
                  <p class="mono vid">{t('cmp.version_label')} {shortId(head.id)}</p>
                </footer>
              </div>
            {:else if col?.status === 'ok'}
              <div class="col-state ui">
                <p class="muted">{t('cmp.no_head')}</p>
                <button class="btn btn-quiet" onclick={() => removeConcept(conceptId)}>
                  {t('cmp.remove_column')}
                </button>
              </div>
            {:else if col?.status === 'error'}
              <div class="col-state ui">
                <p class="error" role="alert">{t('cmp.fetch_failed', { error: col.message })}</p>
                <button class="btn btn-quiet" onclick={() => removeConcept(conceptId)}>
                  {t('cmp.remove_column')}
                </button>
              </div>
            {:else}
              <div class="col-state ui">
                <p class="muted"><span class="spinner" aria-hidden="true"></span> {t('cmp.loading_concept')}</p>
              </div>
            {/if}
          </section>
        {/each}
      </div>
    </div>

    {#if ids.length === 1}
      <p class="ui muted single-hint">
        {t('cmp.single_hint')}
      </p>
    {/if}
  {/if}
</div>

<style>

  /* ── Toolbar ── */
  .toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
    padding: var(--space-3) 0;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
  }

  .spacer {
    flex: 1;
  }

  /* A <button class="btn"> doesn't get a.btn's global inline-flex — align the
     sparkle icon with its label locally. */
  .harmonise-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
  }

  .diff-toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 500;
    padding: 0.35em 0.8em;
    border: 1px solid var(--line);
    border-radius: var(--radius-pill);
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .diff-toggle.on {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .diff-toggle input {
    accent-color: var(--accent);
    margin: 0;
  }

  .add {
    position: relative;
    min-width: 240px;
  }

  /* Deliberate deviation on .input: the quick-add search is pill-shaped. */
  .add input {
    width: 100%;
    border-radius: var(--radius-pill);
  }

  .add-results {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 0;
    z-index: 60;
    width: min(380px, 90vw);
    padding: var(--space-2);
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .add-results .muted {
    margin: var(--space-1) var(--space-2);
  }

  .add-hit {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    text-align: left;
    cursor: pointer;
  }

  .add-hit:hover {
    background: var(--accent-soft);
  }

  .hit-form {
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .hit-coll {
    color: var(--ink-3);
  }

  /* ── Harmonise panel ── */
  .harmonise {
    margin-bottom: var(--space-6);
    border-color: var(--accent);
    background:
      radial-gradient(ellipse at 15% 0%, var(--accent-soft), transparent 55%),
      var(--bg-raised);
  }

  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .panel-head h2 {
    margin-bottom: var(--space-2);
  }

  .panel-sub {
    color: var(--ink-2);
    max-width: 68ch;
    font-size: var(--text-sm);
  }

  .field {
    display: block;
    margin-bottom: var(--space-3);
    font-size: var(--text-sm);
  }

  .field > span {
    display: block;
    margin-bottom: var(--space-1);
    font-weight: 600;
  }

  .field input,
  .field textarea {
    width: 100%;
  }

  .field textarea {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .preset-pick select {
    width: 100%;
  }

  .preset-save {
    margin-bottom: var(--space-3);
    font-size: var(--text-sm);
  }

  .preset-open {
    padding-left: 0;
    color: var(--accent);
  }

  .preset-form {
    border: 1px dashed var(--line);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
    background: var(--bg);
  }

  .preset-form .row {
    margin-bottom: 0;
  }

  .preset-name {
    margin-bottom: var(--space-2);
  }

  .preset-shared {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
    cursor: pointer;
  }

  .preset-shared input {
    accent-color: var(--accent);
    margin: 0;
  }

  .saved-inline {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    margin: var(--space-2) 0 0;
    color: var(--ins-strong);
  }

  .review {
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--line);
  }

  .prov {
    color: var(--accent);
    margin-bottom: var(--space-3);
  }

  .row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-2);
  }

  .hint {
    font-size: var(--text-sm);
  }

  .saved {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.35em;
    margin: var(--space-2) 0 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--ins-strong);
    border-radius: var(--radius-sm);
    background: var(--ins-wash);
  }

  /* ── Workbench ── */
  .legend {
    display: flex;
    gap: var(--space-4);
    color: var(--ink-3);
    margin-bottom: var(--space-3);
  }

  /* Kontraktets princip 8: sidan ligger i standardbredd; enbart
     kolumnrullaren bryter ut via den globala .full-bleed och äger sin egen
     horisontalscroll. Spåret (.cols) är max-content med auto-marginaler —
     centrerat när kolumnerna ryms, växer från mitten utåt och scrollar
     först när de fyller mer än hela sidbredden. */
  .workbench {
    overflow: auto;
    max-height: calc(100vh - 230px);
    padding-bottom: var(--space-2);
    scrollbar-width: thin;
  }

  .cols {
    display: flex;
    gap: var(--space-4);
    width: max-content;
    margin-inline: auto;
    padding-inline: var(--space-6);
    align-items: stretch;
  }

  .col {
    width: min(380px, 82vw);
    flex: 0 0 auto;
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    display: flex;
    flex-direction: column;
  }

  .col.is-base {
    border-color: var(--accent);
    box-shadow: var(--shadow-sm);
  }

  .col-head {
    position: sticky;
    top: 0;
    z-index: 2;
    padding: var(--space-4) var(--space-6) var(--space-3);
    background: var(--bg-raised);
    border-bottom: 1px solid var(--line);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }

  .col.is-base .col-head {
    background:
      linear-gradient(var(--accent-soft), var(--accent-soft)),
      var(--bg-raised);
  }

  .col-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
  }

  .base-pick {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--ink-3);
    cursor: pointer;
  }

  .col.is-base .base-pick {
    color: var(--accent);
  }

  .base-pick input {
    accent-color: var(--accent);
    margin: 0;
  }

  .remove {
    font-size: var(--text-base);
    line-height: 1;
    padding: 0.15em 0.45em;
    color: var(--ink-3);
  }

  .remove:hover {
    color: var(--del-strong);
  }

  .col-head h2 {
    margin-bottom: var(--space-1);
  }

  .col-head h2 a {
    color: inherit;
    text-decoration: none;
  }

  .col-head h2 a:hover {
    text-decoration: underline;
    text-decoration-color: var(--accent);
  }

  .coll {
    color: var(--ink-3);
    margin-bottom: var(--space-2);
  }

  .pills {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }

  .col-body {
    padding: var(--space-4) var(--space-6) var(--space-4);
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .def {
    font-size: var(--text-base);
    line-height: 1.7;
    flex: 1;
  }

  .def.plain {
    white-space: pre-wrap;
    margin: 0 0 var(--space-4);
  }

  .s.del {
    background: var(--del-wash);
    color: var(--del-strong);
    text-decoration: line-through;
    text-decoration-thickness: 1px;
    border-radius: var(--radius-sm);
  }

  .s.ins {
    background: var(--ins-wash);
    box-shadow: inset 0 -2px 0 var(--ins-strong);
    border-radius: var(--radius-sm);
  }

  .legend .s {
    padding: 0 0.35em;
  }

  .col-foot {
    margin-top: auto;
    padding-top: var(--space-3);
    border-top: 1px solid var(--line);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .col-foot p {
    margin: 0 0 var(--space-1);
  }

  .vid {
    color: var(--ink-3);
  }

  .col-state {
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    align-items: flex-start;
  }

  .single-hint {
    margin-top: var(--space-4);
  }

  .state-card {
    max-width: 620px;
  }

  .state-card p {
    margin: 0;
  }

  .muted {
    color: var(--ink-3);
  }

  .error {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-sm);
    background: var(--del-wash);
    margin: 0 0 var(--space-3);
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
