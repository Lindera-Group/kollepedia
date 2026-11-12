<script lang="ts">
  /** The Lägg i lista tool subview (extracted 2026-07-12): the lists already
   * holding this concept + the inline add-to-list flow, loaded on mount. */
  import { api, type ConceptOut, type ListItemOut, type ListOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import AddToList from '$lib/lists/AddToList.svelte';
  import { pinLabel } from '$lib/lists/pin';

  interface Props {
    concept: ConceptOut & { head: NonNullable<ConceptOut['head']> };
    /** Fires after a successful add so the owner bumps its list counter. */
    onadded: () => void;
  }

  let { concept, onadded }: Props = $props();

  let myLists = $state<ListOut[] | null>(null);
  let myListsError = $state<string | null>(null);

  async function loadMyLists(): Promise<void> {
    myListsError = null;
    try {
      const all = await api.lists();
      myLists = all.filter((l) => l.items.some((it) => it.concept_id === concept.id));
    } catch (e) {
      myLists = [];
      myListsError = errorMessage(e);
    }
  }

  $effect(() => {
    void loadMyLists();
  });

  function listItemFor(list: ListOut): ListItemOut {
    return (
      list.items.find((it) => it.concept_id === concept.id) ?? {
        id: '',
        concept_id: concept.id,
        version_id: null,
        follow_head: true,
        ordinal: 0,
        note: null,
        canonical_form: null
      }
    );
  }

  function handleAdded(): void {
    onadded();
    void loadMyLists();
  }
</script>

<h3 class="subview-h ui">{t('list.add_button')}</h3>
{#if myLists === null}
  <p class="muted ui" role="status">{t('list.loading_lists')}</p>
{:else if myListsError}
  <p class="err ui" role="alert">{t('lists.load_error', { error: myListsError })}</p>
{:else if myLists.length}
  <p class="subview-hint ui">{t('cpage.tool_lists_heading')}</p>
  <ul class="lists-in">
    {#each myLists as list (list.id)}
      <li>
        <a href="/lists/{list.id}">{list.name}</a>
        <span class="mono">{pinLabel(listItemFor(list))}</span>
      </li>
    {/each}
  </ul>
{/if}
<AddToList inline conceptId={concept.id} versionId={concept.head.id} onadded={handleAdded} />

<style>
  .muted {
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  .err {
    color: var(--del-strong);
    font-size: var(--text-sm);
  }

  .lists-in {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .lists-in li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    font-size: var(--text-sm);
  }

  .lists-in .mono {
    font-size: var(--text-xs);
    color: var(--ink-3);
  }
</style>
