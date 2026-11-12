<script lang="ts">
  /** The one page-title block (ui-guardrails §15). Drop this at the top of
   * every page's `.container` so the heading rhythm, intro treatment and
   * action row are identical everywhere — new pages follow the design
   * guideline by construction instead of hand-rolling a `.page-head`.
   *
   *   <PageHeader title={t('prop.h1')} intro={t('prop.intro')} />
   *
   * Rich lead content (links inside the intro) goes in the default slot;
   * header-level actions (cross-links, buttons) go in the `actions` snippet.
   * All styling comes from the global `.page-head*` classes in app.css — this
   * component adds none of its own. */
  import type { Snippet } from 'svelte';

  let {
    title,
    intro,
    actions,
    children
  }: {
    title: string;
    /** Plain lead paragraph. For rich content (links) use the default slot. */
    intro?: string;
    /** Header-right action row — cross-links or buttons. */
    actions?: Snippet;
    /** Rich lead content rendered below the title row. */
    children?: Snippet;
  } = $props();
</script>

<header class="page-head">
  <div class="page-head-row">
    <h1>{title}</h1>
    {#if actions}
      <div class="page-head-actions">{@render actions()}</div>
    {/if}
  </div>
  {#if intro}
    <p class="page-head-intro">{intro}</p>
  {/if}
  {#if children}
    {@render children()}
  {/if}
</header>
