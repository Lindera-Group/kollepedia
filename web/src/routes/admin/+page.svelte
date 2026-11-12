<script lang="ts">
  /** Administration hub — THE one place that gathers every admin and
   * superadmin surface (ui-guardrails §15). Reads the section map from
   * $lib/admin/adminNav so a new tool appears here (and in the nav gate) by
   * adding one entry, never another orphan route. Sections/items are pruned
   * to what the current session may act on; non-admins get the access guard. */
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';
  import { canSeeAdminHub, visibleAdminSections } from '$lib/admin/adminNav';

  const allowed = $derived(canSeeAdminHub());
  const sections = $derived(visibleAdminSections());
</script>

<svelte:head><title>{t('admin.head_title')}</title></svelte:head>

<div class="container">
  {#if !allowed}
    <div class="card guard ui">
      <h1>{t('admin.guard_h1')}</h1>
      <p>
        {t('admin.guard_body')}
        {#if !currentUser.handle}
          {t('admin.guard_login')}
        {:else}
          {t('admin.guard_no_rights')}
        {/if}
      </p>
      <p><a href="/">{t('common.to_home')}</a></p>
    </div>
  {:else}
    <PageHeader title={t('admin.h1')} intro={t('admin.intro')} />

    {#each sections as section (section.id)}
      <section class="admin-section">
        <div class="admin-section-head">
          <h2>{t(section.title)}</h2>
          <p class="admin-section-desc ui">{t(section.desc)}</p>
        </div>
        <div class="card-grid">
          {#each section.items as item (item.href)}
            <a class="card hub-card" href={item.href}>
              <span class="hub-icon" aria-hidden="true">
                <Icon name={item.icon} size={20} />
              </span>
              <span class="hub-body">
                <span class="hub-title">{t(item.title)}</span>
                <span class="hub-desc ui">{t(item.desc)}</span>
              </span>
            </a>
          {/each}
        </div>
      </section>
    {/each}
  {/if}
</div>

<style>
  .admin-section {
    margin-bottom: var(--space-8);
  }

  .admin-section-head {
    margin-bottom: var(--space-4);
  }

  .admin-section-head h2 {
    margin-bottom: var(--space-1);
  }

  .admin-section-desc {
    max-width: 68ch;
    margin: 0;
    color: var(--ink-3);
    font-size: var(--text-sm);
  }

  /* Composes on the global .card — a whole-card link to one admin surface. */
  .hub-card {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    text-decoration: none;
    color: var(--ink);
    transition:
      border-color 0.15s var(--ease-out),
      box-shadow 0.15s var(--ease-out),
      transform 0.1s var(--ease-out);
  }

  .hub-card:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
  }

  .hub-card:active {
    transform: translateY(1px);
  }

  .hub-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
    background: var(--accent-soft);
    color: var(--accent);
  }

  .hub-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
  }

  .hub-title {
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    font-weight: 560;
    letter-spacing: -0.01em;
    color: var(--ink);
  }

  .hub-desc {
    font-size: var(--text-sm);
    line-height: 1.55;
    color: var(--ink-3);
  }
</style>
