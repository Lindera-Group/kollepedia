<script lang="ts">
  /** Samlingsöversikten — v1:s grupperade hantering (CollectionsView, spegel
   * 2026-07-16): inloggade ser sektioner från litet till stort scope (Mina →
   * Organisationssamlingar → Publika), superadmin får två extra grupper så
   * inget försvinner ur vyn. Anonyma ser den platta publika listan. Korten
   * speglar v1:s anatomi: namn, kort beskrivning, metarad med synlighetsord
   * (Intern/Publik — hänglåset är vikt för "Låst") · år · licens · credits ·
   * antal begrepp. Egna samlingar är alltid privata; Dela-knappen leder till
   * sidan som förklarar organisationsvägen. */
  import { i18n, formatNumber, t } from '$lib/i18n.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { localizedCollection } from '$lib/collections/locale';
  import { currentUser } from '$lib/user.svelte';
  import { api, type CollectionOut } from '$lib/api';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  // SSR seedar den publika listan (ingen session på servern). Med inloggad
  // session hämtas listan om med Bearer-token så privata och org-interna
  // samlingar dyker upp — samma mönster som detaljsidans login-retry.
  let sessionList = $state<CollectionOut[] | null>(null);
  $effect(() => {
    if (!currentUser.handle) {
      sessionList = null;
      return;
    }
    api
      .collections()
      .then((list) => (sessionList = list))
      .catch(() => (sessionList = null));
  });

  const collections = $derived(sessionList ?? data.collections);
  const loadError = $derived(data.loadError);

  const loggedIn = $derived(currentUser.handle !== '');
  const myOrgIds = $derived(new Set(currentUser.memberships.map((m) => m.id)));

  type Group = 'mine' | 'org' | 'public' | 'other_org' | 'other_user';

  /** v1:s gruppregel: egen sandlåda före org före publikt — en samling hamnar
   * i exakt en grupp. Servern har redan filtrerat bort det osynliga. */
  function groupOf(c: CollectionOut): Group {
    if (c.visibility === 'private' && c.created_by === currentUser.handle) return 'mine';
    if (c.organisation && myOrgIds.has(c.organisation.id)) return 'org';
    if (c.visibility === 'public') return 'public';
    if (currentUser.is_super_admin && c.visibility === 'org_private') return 'other_org';
    if (currentUser.is_super_admin && c.visibility === 'private') return 'other_user';
    return 'public';
  }

  function byName(a: CollectionOut, b: CollectionOut): number {
    return localizedCollection(a, i18n.lang).name.localeCompare(
      localizedCollection(b, i18n.lang).name,
      'sv'
    );
  }

  function ofGroup(group: Group): CollectionOut[] {
    return collections.filter((c) => groupOf(c) === group).toSorted(byName);
  }

  function groupByKey(
    list: CollectionOut[],
    keyFn: (c: CollectionOut) => string
  ): { key: string; items: CollectionOut[] }[] {
    const map = new Map<string, CollectionOut[]>();
    for (const item of list) {
      const key = keyFn(item);
      const bucket = map.get(key);
      if (bucket) bucket.push(item);
      else map.set(key, [item]);
    }
    return [...map.entries()]
      .sort((a, b) => a[0].localeCompare(b[0], 'sv'))
      .map(([key, items]) => ({ key, items }));
  }

  const mine = $derived(loggedIn ? ofGroup('mine') : []);
  const orgGroups = $derived(
    loggedIn ? groupByKey(ofGroup('org'), (c) => c.organisation?.name ?? '?') : []
  );
  const publicCollections = $derived(loggedIn ? ofGroup('public') : collections);
  const otherOrgGroups = $derived(
    currentUser.is_super_admin
      ? groupByKey(ofGroup('other_org'), (c) => c.organisation?.name ?? '?')
      : []
  );
  const otherUserGroups = $derived(
    currentUser.is_super_admin
      ? groupByKey(ofGroup('other_user'), (c) => c.created_by ?? '?')
      : []
  );

  /** Synlighetsvärdet med detaljsidans ordval (metadata-dl:ens dd). */
  function visibilityValue(c: CollectionOut): string {
    if (c.visibility === 'org_private') return t('coll.visibility_org_value');
    if (c.visibility === 'private') return t('coll.visibility_private_value');
    return t('coll.visibility_public_value');
  }

  /** Metaraden är detaljsidans metadata-dl i miniatyr — samma rubriker och
   * värden i samma ordning (År, Begrepp, Licens, Synlighet,
   * Redigeringspolicy), ett storlekssnäpp mindre. */
  function metaEntries(c: CollectionOut): { label: string; value: string }[] {
    const entries: { label: string; value: string }[] = [];
    if (c.year) entries.push({ label: t('coll.year_label'), value: String(c.year) });
    entries.push({ label: t('coll.meta_concepts'), value: formatNumber(c.concept_count) });
    const licenceLabel = c.licence?.label;
    if (typeof licenceLabel === 'string' && licenceLabel) {
      entries.push({ label: t('coll.licence_label'), value: licenceLabel });
    }
    entries.push({ label: t('coll.visibility_label'), value: visibilityValue(c) });
    if (c.edit_policy) {
      entries.push({
        label: t('coll.policy_label'),
        value: c.edit_policy === 'org' ? t('coll.policy_org') : t('coll.policy_anyone')
      });
    }
    return entries;
  }
</script>

<svelte:head>
  <title>{t('coll.index_head_title')}</title>
  <meta name="description" content={t('coll.index_intro')} />
</svelte:head>

{#snippet collCard(collection: CollectionOut, shareable: boolean)}
  {@const loc = localizedCollection(collection, i18n.lang)}
  {@const short = loc.short ?? collection.description}
  <div class="card-wrap" class:shareable>
    <a class="coll-card" href="/collections/{collection.slug}">
      <h3>
        {loc.name}
        {#if collection.is_locked}
          <span class="locked-mark" title={t('coll.locked_badge_title')}
            ><Icon name="lock" filled size={13} /></span
          >
        {/if}
      </h3>
      {#if short}
        <p class="short">{short}</p>
      {/if}
      <dl class="meta ui">
        {#each metaEntries(collection) as entry (entry.label)}
          <div><dt>{entry.label}</dt><dd>{entry.value}</dd></div>
        {/each}
      </dl>
    </a>
    {#if shareable}
      <a class="share-link btn ui" href="/collections/share" title={t('coll.share_btn_title')}
        >{t('coll.share_btn')}</a
      >
    {/if}
  </div>
{/snippet}

<div class="container">
  <PageHeader title={t('nav.collections')} intro={t('coll.index_intro')}>
    {#snippet actions()}
      {#if loggedIn}
        <a class="btn ui" href="/new-collection" title={t('home.new_collection_title')}
          >{t('home.new_collection')}</a
        >
      {/if}
    {/snippet}
  </PageHeader>

  {#if loadError}
    <p class="error ui">{t('home.api_error', { error: loadError })}</p>
  {/if}

  {#if loggedIn}
    <section aria-labelledby="grp-mine">
      <h2 id="grp-mine" class="group-title mono">{t('coll.group_mine')}</h2>
      {#if mine.length === 0}
        <p class="empty muted ui">{t('coll.group_mine_empty')}</p>
      {:else}
        <div class="grid">
          {#each mine as collection (collection.id)}
            {@render collCard(collection, true)}
          {/each}
        </div>
      {/if}
    </section>

    {#if currentUser.memberships.length > 0}
      <section aria-labelledby="grp-org">
        <h2 id="grp-org" class="group-title mono">{t('coll.group_org')}</h2>
        {#if orgGroups.length === 0}
          <p class="empty muted ui">{t('coll.group_org_empty')}</p>
        {:else}
          {#each orgGroups as group (group.key)}
            <h3 class="org-name ui">{group.key}</h3>
            <div class="grid">
              {#each group.items as collection (collection.id)}
                {@render collCard(collection, false)}
              {/each}
            </div>
          {/each}
        {/if}
      </section>
    {/if}

    <section aria-labelledby="grp-public">
      <h2 id="grp-public" class="group-title mono">{t('coll.group_public')}</h2>
      {#if publicCollections.length === 0}
        <p class="empty muted ui">{t('coll.group_public_empty')}</p>
      {:else}
        <div class="grid">
          {#each publicCollections as collection (collection.id)}
            {@render collCard(collection, false)}
          {/each}
        </div>
      {/if}
    </section>

    {#if otherOrgGroups.length > 0}
      <section aria-labelledby="grp-other-orgs">
        <h2 id="grp-other-orgs" class="group-title mono">{t('coll.group_other_orgs')}</h2>
        {#each otherOrgGroups as group (group.key)}
          <h3 class="org-name ui">{group.key}</h3>
          <div class="grid">
            {#each group.items as collection (collection.id)}
              {@render collCard(collection, false)}
            {/each}
          </div>
        {/each}
      </section>
    {/if}

    {#if otherUserGroups.length > 0}
      <section aria-labelledby="grp-other-users">
        <h2 id="grp-other-users" class="group-title mono">{t('coll.group_other_users')}</h2>
        {#each otherUserGroups as group (group.key)}
          <h3 class="org-name mono">{group.key}</h3>
          <div class="grid">
            {#each group.items as collection (collection.id)}
              {@render collCard(collection, false)}
            {/each}
          </div>
        {/each}
      </section>
    {/if}
  {:else}
    <div class="grid">
      {#each publicCollections as collection (collection.id)}
        {@render collCard(collection, false)}
      {/each}
    </div>
  {/if}
</div>

<style>
  section {
    margin-bottom: var(--space-12);
  }

  /* Samma grupprubrik som /pricing — mono-versal, dämpad. */
  .group-title {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--ink-3);
    font-weight: 400;
    margin: 0 0 var(--space-3);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--line);
  }

  .org-name {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--ink-2);
    margin: var(--space-4) 0 var(--space-2);
  }

  .empty {
    margin: 0;
    font-size: var(--text-sm);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--space-4);
  }

  .card-wrap {
    position: relative;
    display: flex;
  }

  .coll-card {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-6);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    background: var(--bg-raised);
    text-decoration: none;
    color: inherit;
    transition: border-color 0.15s, transform 0.15s;
  }

  .coll-card:hover {
    border-color: var(--ink);
    transform: translateY(-2px);
  }

  .coll-card h3 {
    font-size: var(--text-lg);
    font-family: var(--font-serif);
    font-weight: 600;
    line-height: 1.3;
    margin: 0;
  }

  /* Dela-knappen ligger ovanpå ankaret (giltigt utan nästlade länkar). */
  .card-wrap.shareable .coll-card h3 {
    padding-right: var(--space-12);
  }

  .share-link {
    position: absolute;
    top: var(--space-4);
    right: var(--space-4);
    font-size: var(--text-xs);
    padding: 0.3em 0.8em;
  }

  .locked-mark {
    display: inline-flex;
    vertical-align: baseline;
    color: var(--ink-3);
  }

  .short {
    flex: 1;
    color: var(--ink-2);
    font-size: var(--text-sm);
    line-height: 1.55;
    margin: 0;
  }

  /* Detaljsidans .metadata-dl, ett snäpp mindre (2xs-etiketter, xs-värden). */
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-4);
    margin: 0;
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }

  .meta div {
    display: flex;
    gap: var(--space-1);
    align-items: baseline;
  }

  .meta dt {
    font-size: var(--text-2xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .meta dd {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--ink);
  }

  .error {
    padding: var(--space-4);
    border: 1px solid var(--del-strong);
    border-radius: var(--radius-md);
    background: var(--del-wash);
    margin-bottom: var(--space-6);
  }
</style>
