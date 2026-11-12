<script lang="ts">
  /** The one way to mention an author: display name linked to the public
   * author page (/authors/{handle}). The author page soft-renders for
   * unknown/hidden handles, so the link never dead-ends. Null/undefined
   * user renders the fallback text (default: unknown author). */
  import { t } from '$lib/i18n.svelte';

  let {
    user,
    fallback
  }: {
    user: { handle: string; display_name: string } | null | undefined;
    fallback?: string;
  } = $props();
</script>

{#if user}<a class="author-link" href="/authors/{user.handle}">{user.display_name}</a
  >{:else}{fallback ?? t('tm.unknown_author')}{/if}

<style>
  /* Quiet link: reads as text in bylines and meta rows, reveals itself on
     hover — the pattern set by the concept page byline (beslut 2026-07-12). */
  .author-link {
    color: inherit;
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, currentColor 45%, transparent);
  }

  .author-link:hover {
    color: var(--accent);
    text-decoration-color: currentColor;
  }
</style>
