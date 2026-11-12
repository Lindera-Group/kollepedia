<script lang="ts">
  /** Begreppskortet enligt v1:s anatomi (designkontraktets princip 7,
   * 2026-07-14): titelrad + språkmärke, definitionsutdrag med KLICKBARA
   * korsreferenser (länkbevarande snippet från backend), kategorirad och
   * en tydlig samlingsbadge (CollectionBadge — "the v1-inherited badge").
   * Kortet är en div med stretched-link på titeln så inre länkar förblir
   * giltiga och klickbara (aldrig <a> i <a>). */
  import type { ConceptListItem } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import CollectionBadge from './CollectionBadge.svelte';
  import { statusLabel, t } from '$lib/i18n.svelte';
  import { renderMarkdown } from '$lib/text';

  interface Props {
    concept: ConceptListItem;
  }

  let { concept }: Props = $props();

  const snippetHtml = $derived(
    renderMarkdown(concept.definition_snippet_md || concept.definition_snippet)
  );
  const visibleCategories = $derived(concept.categories.slice(0, 4));
  const visibleTags = $derived(
    concept.tags.slice(0, Math.max(0, 4 - concept.categories.length))
  );
</script>

<article class="concept-card">
  <div class="head">
    <h3><a class="card-link" href="/concepts/{concept.id}">{concept.canonical_form}</a></h3>
    <span class="mono lang">{concept.language.toUpperCase()}</span>
  </div>

  <div class="snippet">{@html snippetHtml}</div>

  <div class="foot ui">
    {#if visibleCategories.length > 0 || visibleTags.length > 0}
      <div class="cats">
        {#each visibleCategories as category (category)}
          <span class="cat-pill">{category}</span>
        {/each}
        {#each visibleTags as tag (tag)}
          <span class="tag-pill">#{tag}</span>
        {/each}
      </div>
    {/if}
    <div class="coll-row">
      <CollectionBadge
        collection={{
          slug: concept.collection_slug,
          name: concept.collection_name,
          year: concept.collection_year,
          visibility: concept.collection_visibility,
          has_org: concept.collection_has_org
        }}
      />
      <span class="pill pill-status-{concept.status}">{statusLabel(concept.status)}</span>
      {#if concept.version_count > 1}
        <span class="versions mono" title={t('concept_card.versions_title')}><Icon name="clock" size={13} /> {concept.version_count}</span>
      {/if}
    </div>
  </div>
</article>

<style>
  .concept-card {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: var(--space-4) var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
  }

  .concept-card:hover {
    border-color: var(--ink);
    transform: translateY(-1px);
    box-shadow: var(--shadow-sm);
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-3);
  }

  h3 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-lg);
  }

  .card-link {
    color: inherit;
    text-decoration: none;
  }

  /* Stretched link: hela kortet klickbart via titelns länk. */
  .card-link::after {
    content: '';
    position: absolute;
    inset: 0;
  }

  .lang {
    color: var(--ink-3);
    letter-spacing: 0.05em;
  }

  .snippet {
    color: var(--ink-2);
    font-size: var(--text-sm);
    line-height: 1.55;
    margin-bottom: var(--space-3);
  }

  .snippet :global(p) {
    margin: 0;
  }

  /* Inre länkar (korsreferenser) lyfts ovanpå stretched-linken. */
  .snippet :global(a) {
    position: relative;
    z-index: 1;
  }

  .foot {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-xs);
  }

  .cats {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .coll-row {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .versions {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    color: var(--accent);
  }
</style>
