<script lang="ts">
  /** The v1-inherited collection badge (begreppssidans verktygsyta,
   * 2026-07-10): sunken plate, scope icon (book = public, group =
   * org-owned, person = personal org_private without an organisation —
   * see ncoll.org_hint), a lock overlay when the collection is locked,
   * "Name · year", inverts to ink-on-bg on hover. Links to the collection. */
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';

  /** Strukturellt minimum — CollectionOut passar, men begreppskorten
   * (kontraktets princip 7) skickar bara slug/name/year; scope-ikonen
   * faller då tillbaka till book (publik). */
  type BadgeCollection = {
    slug: string;
    name: string;
    year?: number | null;
    visibility?: string;
    organisation?: { name: string } | null;
    /** Lättviktsflagga för listytor som inte bär hela org-objektet. */
    has_org?: boolean;
    is_locked?: boolean;
  };

  let { collection }: { collection: BadgeCollection } = $props();

  const scopeIcon = $derived.by((): 'book' | 'group' | 'person' => {
    if (collection.visibility !== 'org_private') return 'book';
    return collection.organisation || collection.has_org ? 'group' : 'person';
  });

  const scopeTitle = $derived(
    collection.visibility !== 'org_private'
      ? t('cpage.badge_scope_public')
      : collection.organisation
        ? t('cpage.badge_scope_org')
        : t('cpage.badge_scope_personal')
  );

  const title = $derived(
    collection.is_locked ? `${scopeTitle} · ${t('cpage.badge_locked_suffix')}` : scopeTitle
  );

  // Built as one string (not `{name}{#if year} · {year}{/if}`) — Svelte
  // trims the leading space of a text node that opens a block, which
  // silently swallowed the separator here.
  const label = $derived(collection.year ? `${collection.name} · ${collection.year}` : collection.name);
</script>

<a
  class="coll-badge ui"
  class:scope-org={scopeIcon === 'group'}
  class:scope-person={scopeIcon === 'person'}
  href="/collections/{collection.slug}"
  {title}
>
  <span class="badge-icon"><Icon name={scopeIcon} size={13} /></span>
  {#if collection.is_locked}
    <Icon name="lock" filled size={12} />
  {/if}
  <span class="name">{label}</span>
</a>

<style>
  .coll-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4em;
    background: var(--bg-sunken);
    border: 1px solid var(--line);
    color: var(--ink-2);
    padding: 0.22em 0.75em;
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    font-weight: 500;
    line-height: 1.4;
    text-decoration: none;
    transition: background-color 0.15s, color 0.15s;
  }

  .coll-badge:hover,
  .coll-badge:focus-visible {
    background: var(--ink);
    color: var(--bg);
  }

  /* Typfärger per scope (v1): org-intern = amber, personlig = streckad/dämpad,
     publik = neutral plate. Färgerna är semantik, aldrig dekoration. */
  .coll-badge.scope-org {
    background: var(--scope-org-wash);
    border-color: color-mix(in srgb, var(--scope-org-ink) 45%, transparent);
    color: var(--scope-org-ink);
  }

  .coll-badge.scope-person {
    border-style: dashed;
    color: var(--ink-3);
  }

  .name {
    white-space: nowrap;
  }

  /* The icon must not stretch the line-box past the pill height. */
  .badge-icon {
    display: inline-flex;
    max-height: 1em;
    align-items: center;
  }
</style>
