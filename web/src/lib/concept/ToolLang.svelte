<script lang="ts">
  /** The Översätt tool subview (extracted 2026-07-12): existing translations,
   * the create-translation entry, and the link-to-existing search visible
   * immediately with a collection-scope toggle (same collection default). */
  import { api, type ConceptListItem, type ConceptOut } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import ConceptCombobox from '$lib/edit/ConceptCombobox.svelte';
  import { errorMessage } from '$lib/errors';
  import { languageLabel, t } from '$lib/i18n.svelte';
  import { stripMarkdown } from '$lib/text';

  interface Props {
    concept: ConceptOut & { head: NonNullable<ConceptOut['head']> };
    canWrite: boolean;
    writeBlocked: boolean;
    /** Fires after a successful link so the owner refetches the concept. */
    onchanged: () => void;
  }

  let { concept, canWrite, writeBlocked, onchanged }: Props = $props();

  const otherLanguage = $derived(concept.head.language === 'sv' ? 'en' : 'sv');

  let linkScope = $state<'same' | 'all'>('same');
  let linkTarget = $state<ConceptOut | null>(null);
  let linkLoading = $state(false);
  let linkSaving = $state(false);
  let linkError = $state<string | null>(null);
  let linkDone = $state<string | null>(null);

  async function pickTranslation(item: ConceptListItem): Promise<void> {
    linkError = null;
    linkLoading = true;
    try {
      const target = await api.concept(item.id);
      if (!target.head) {
        linkError = t('concept.link_target_missing_head');
      } else {
        linkTarget = target;
      }
    } catch (e) {
      linkError = errorMessage(e);
    } finally {
      linkLoading = false;
    }
  }

  async function confirmLink(): Promise<void> {
    if (!linkTarget?.head || linkSaving) return;
    linkSaving = true;
    linkError = null;
    try {
      await api.createVersion(concept.id, {
        mode: 'translate',
        base_version_id: concept.head.id,
        canonical_form: concept.head.canonical_form,
        definition_md: concept.head.definition_md,
        source_version_id: linkTarget.head.id,
        note: t('concept.note_linked_translation', { term: linkTarget.head.canonical_form })
      });
      linkDone = linkTarget.head.canonical_form;
      linkTarget = null;
      onchanged();
    } catch (e) {
      linkError = errorMessage(e);
    } finally {
      linkSaving = false;
    }
  }
</script>

<h3 class="subview-h ui">{t('cpage.tool_lang')}</h3>
<p class="subview-hint ui">{t('concept.translate_hint')}</p>

{#if concept.translations.length > 0}
  <ul class="lang-list">
    {#each concept.translations as translation (translation.concept_id)}
      <li>
        <span class="langcode">{translation.language.toUpperCase()}</span>
        <a href="/concepts/{translation.concept_id}">{translation.canonical_form}</a>
        <span class="mono">{languageLabel(translation.language)}</span>
      </li>
    {/each}
  </ul>
{/if}

{#if linkDone}
  <p class="link-confirm ui" role="status">
    <Icon name="check" size={14} /> {t('concept.translation_linked', { name: linkDone })}
  </p>
{/if}

{#if canWrite && !writeBlocked}
  <div class="subview-actions">
    <a
      class="btn btn-primary"
      href="/new-concept?translate_from={concept.head.id}&collection={concept.collection.slug}"
      title={t('concept.create_translation_title', { lang: languageLabel(otherLanguage) })}
    >
      {t('concept.create_translation')}
    </a>
  </div>

  <div class="link-existing">
    <h4 class="subview-h ui">{t('concept.link_translation')}</h4>
    {#if !linkTarget}
      <div class="scope-row ui" role="group" aria-label={t('concept.link_scope_aria')}>
        <button
          type="button"
          class="filter-chip"
          aria-pressed={linkScope === 'same'}
          onclick={() => (linkScope = 'same')}
        >{t('concept.link_scope_same')}</button>
        <button
          type="button"
          class="filter-chip"
          aria-pressed={linkScope === 'all'}
          onclick={() => (linkScope = 'all')}
        >{t('concept.link_scope_all')}</button>
      </div>
      <ConceptCombobox
        language={otherLanguage}
        collection={linkScope === 'same' ? concept.collection.slug : undefined}
        excludeId={concept.id}
        inputId="translation-combobox"
        onselect={pickTranslation}
        disabled={linkLoading || linkSaving}
      />
      {#if linkLoading}
        <p class="link-hint ui" role="status">{t('concept.loading_concept')}</p>
      {/if}
    {:else if linkTarget.head}
      <div class="link-preview">
        <div class="side">
          <span class="mono lang">{languageLabel(concept.head.language)}</span>
          <strong>{concept.head.canonical_form}</strong>
          <span class="snippet">{stripMarkdown(concept.head.definition_md).slice(0, 140)}</span>
        </div>
        <span class="arrow" aria-hidden="true">⇄</span>
        <div class="side">
          <span class="mono lang">{languageLabel(linkTarget.head.language)}</span>
          <strong>{linkTarget.head.canonical_form}</strong>
          <span class="snippet">{stripMarkdown(linkTarget.head.definition_md).slice(0, 140)}</span>
          <span class="mono coll">{linkTarget.collection.name}</span>
        </div>
      </div>
      {#if linkError}
        <p class="link-error ui" role="alert">{linkError}</p>
      {/if}
      <div class="subview-actions">
        <button type="button" class="btn btn-primary" disabled={linkSaving} onclick={confirmLink}>
          {linkSaving ? t('concept.linking') : t('concept.link_confirm')}
        </button>
        <button
          type="button"
          class="btn btn-quiet"
          disabled={linkSaving}
          onclick={() => (linkTarget = null)}
        >
          {t('concept.pick_other')}
        </button>
      </div>
    {/if}
    {#if linkError && !linkTarget}
      <p class="link-error ui" role="alert">{linkError}</p>
    {/if}
  </div>
{/if}

<style>
  .lang-list {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .lang-list li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    font-size: var(--text-sm);
  }

  .link-confirm {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: var(--text-sm);
    color: var(--ins-strong);
    margin-bottom: var(--space-3);
  }

  .link-existing {
    margin-top: var(--space-6);
  }

  .scope-row {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .link-hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin-top: var(--space-2);
  }

  .link-error {
    font-size: var(--text-sm);
    color: var(--del-strong);
    margin: var(--space-2) 0;
  }

  .link-preview {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .link-preview .side {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    flex: 1;
    min-width: 0;
    font-size: var(--text-sm);
  }

  .link-preview .lang {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .link-preview .snippet {
    font-size: var(--text-xs);
    color: var(--ink-2);
  }

  .link-preview .coll {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }

  .arrow {
    color: var(--ink-3);
  }
</style>
