<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api, type CollectionOut, type VersionPermalinkOut } from '$lib/api';
  import TagEditor from '$lib/edit/TagEditor.svelte';
  import { errorMessage } from '$lib/errors';
  import DefinitionEditor from '$lib/editor/DefinitionEditor.svelte';
  import { languageLabel, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';

  let collections = $state<CollectionOut[]>([]);
  let loadError = $state<string | null>(null);

  let collectionId = $state('');
  // ?name=<term>: the zero-hit creation chip (paket D2, v1 parity) lands
  // here with the search phrase prefilled as the canonical form.
  let canonicalForm = $state(page.url.searchParams.get('name')?.trim() ?? '');
  let language = $state('sv');
  let definitionMd = $state('');
  let tags = $state<string[]>([]);
  let note = $state('');

  let saving = $state(false);
  let error = $state<string | null>(null);
  let formError = $state<string | null>(null);

  const canWrite = $derived(currentUser.handle !== '');
  const preselectSlug = page.url.searchParams.get('collection');

  // ?translate_from=<version_id>: the "create a translation" entry from a
  // concept's language tool. The new concept links back to the source version
  // (translated_from edge) and defaults to the opposite language.
  const translateFromId = page.url.searchParams.get('translate_from');
  let translateSource = $state<VersionPermalinkOut | null>(null);
  let translateSourceError = $state<string | null>(null);

  $effect(() => {
    if (!translateFromId) return;
    api
      .version(translateFromId)
      .then((source) => {
        translateSource = source;
        language = source.language === 'sv' ? 'en' : 'sv';
      })
      .catch((e) => (translateSourceError = errorMessage(e)));
  });

  $effect(() => {
    api
      .collections()
      .then((all) => {
        collections = all;
        if (!collectionId) {
          const preselected = all.find((c) => c.slug === preselectSlug);
          collectionId = preselected?.id ?? all[0]?.id ?? '';
        }
      })
      .catch((e) => (loadError = errorMessage(e)));
  });

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    formError = null;
    if (!collectionId) {
      formError = t('nc.select_collection_error');
      return;
    }
    if (!canonicalForm.trim()) {
      formError = t('edit.error_no_name');
      return;
    }
    saving = true;
    try {
      const created = await api.createConcept({
        collection_id: collectionId,
        canonical_form: canonicalForm.trim(),
        language,
        definition_md: definitionMd,
        tags,
        note: note.trim() || undefined,
        ...(translateSource ? { translated_from_version_id: translateSource.id } : {})
      });
      await goto(`/concepts/${created.id}`);
    } catch (e) {
      error = errorMessage(e);
      saving = false;
    }
  }
</script>

<svelte:head><title>{t('nc.head_title')}</title></svelte:head>

<div class="container">
  <nav class="ui breadcrumb"><a href="/">{t('common.back_to_search')}</a></nav>

  <PageHeader title={t('nc.h1')} intro={t('nc.intro')} />

  {#if !canWrite}
    <p class="locked ui" role="status">
      {t('nc.locked')}
    </p>
  {/if}

  {#if loadError}
    <p class="error ui" role="alert">{t('nc.collections_error', { error: loadError })}</p>
  {/if}

  {#if translateSource}
    <div class="translate-banner ui" role="note">
      <p>
        {t('nc.translating_from')}
        <a href="/concepts/{translateSource.concept_id}"><strong>{translateSource.canonical_form}</strong></a>
        <span class="mono">({languageLabel(translateSource.language)} · {translateSource.collection.name})</span>
      </p>
      <p class="hint">{t('nc.translating_hint')}</p>
    </div>
  {:else if translateSourceError}
    <p class="error ui" role="alert">{t('nc.translate_source_error', { error: translateSourceError })}</p>
  {/if}

  <form class="new-form" onsubmit={submit} aria-label={t('nc.h1')}>
    <div class="row">
      <div class="field grow">
        <label class="ui" for="new-collection">{t('nc.collection_label')}</label>
        <select id="new-collection" class="input" bind:value={collectionId} disabled={!canWrite || saving}>
          {#each collections as collection (collection.id)}
            <option value={collection.id}
              >{collection.name}{collection.year ? ` (${collection.year})` : ''}</option
            >
          {/each}
        </select>
      </div>

      <div class="field">
        <label class="ui" for="new-language">{t('nc.language_label')}</label>
        <select id="new-language" class="input" bind:value={language} disabled={!canWrite || saving}>
          <option value="sv">{languageLabel('sv')}</option>
          <option value="en">{languageLabel('en')}</option>
        </select>
      </div>
    </div>

    <div class="field">
      <label class="ui" for="new-canonical">{t('edit.canonical_label')}</label>
      <input
        id="new-canonical"
        class="input canonical"
        type="text"
        bind:value={canonicalForm}
        disabled={!canWrite || saving}
        placeholder={t('nc.canonical_placeholder')}
        required
      />
    </div>

    <div class="field">
      <label class="ui" for="new-definition">{t('edit.definition_label')}</label>
      <DefinitionEditor
        inputId="new-definition"
        value={definitionMd}
        onchange={(md) => (definitionMd = md)}
        disabled={!canWrite || saving}
        placeholder={t('nc.definition_placeholder')}
      />
    </div>

    <div class="field">
      <label class="ui" for="new-tags">{t('edit.tags_label')}</label>
      <TagEditor {tags} onchange={(next) => (tags = next)} disabled={!canWrite || saving} inputId="new-tags" />
    </div>

    <div class="field">
      <label class="ui" for="new-note">{t('edit.note_label')} <span class="opt">{t('nc.note_opt')}</span></label>
      <textarea
        id="new-note"
        class="input note"
        rows="2"
        bind:value={note}
        disabled={!canWrite || saving}
      ></textarea>
    </div>

    {#if formError}
      <p class="error ui" role="alert">{formError}</p>
    {/if}
    {#if error}
      <p class="error ui" role="alert">{t('nc.create_failed', { error })}</p>
    {/if}

    <div class="actions ui">
      <button type="submit" class="btn btn-primary" disabled={!canWrite || saving}>
        {saving ? t('common.creating') : t('nc.create')}
      </button>
    </div>
  </form>
</div>

<style>


  .locked {
    max-width: 65ch;
    margin-bottom: var(--space-6);
    padding: var(--space-3) var(--space-4);
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .translate-banner {
    max-width: 65ch;
    margin-bottom: var(--space-6);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
    font-size: var(--text-sm);
  }

  .translate-banner p {
    margin: 0;
  }

  .translate-banner .hint {
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .new-form {
    max-width: 65ch;
  }

  .row {
    display: flex;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  .field {
    margin-bottom: var(--space-4);
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

  .opt {
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
    line-height: 1.6;
    resize: vertical;
  }

  .error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin-bottom: var(--space-4);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
  }
</style>
