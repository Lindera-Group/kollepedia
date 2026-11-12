<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { t } from '$lib/i18n.svelte';
  import { slugify } from '$lib/slug';
  import { adminOrgs, currentUser } from '$lib/user.svelte';

  let name = $state('');
  let slug = $state('');
  let slugTouched = $state(false);
  let description = $state('');
  let year = $state<number | null>(null);
  let licenceLabel = $state('');
  let licenceUrl = $state('');
  let visibility = $state<'public' | 'org_private'>('public');
  let editPolicy = $state<'org' | 'anyone'>('anyone');
  let orgId = $state('');

  let saving = $state(false);
  let error = $state<string | null>(null);

  const canWrite = $derived(currentUser.handle !== '');
  const myAdminOrgs = $derived(adminOrgs());
  // Utan organisation: vanliga användare får en privat sandlåda (beslut 2 —
  // tratten); superadministratörer skapar org-lösa systemsamlingar.
  const sandboxMode = $derived(!currentUser.is_super_admin && !orgId);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    if (!name.trim()) {
      error = t('ncoll.error_name');
      return;
    }
    const finalSlug = slug.trim() || slugify(name);
    if (!finalSlug) {
      error = t('ncoll.error_slug');
      return;
    }
    saving = true;
    try {
      const created = await api.createCollection({
        slug: finalSlug,
        name: name.trim(),
        description: description.trim() || null,
        year: typeof year === 'number' && !Number.isNaN(year) ? year : null,
        licence:
          licenceLabel.trim() || licenceUrl.trim()
            ? {
                ...(licenceLabel.trim() ? { label: licenceLabel.trim() } : {}),
                ...(licenceUrl.trim() ? { url: licenceUrl.trim() } : {})
              }
            : null,
        visibility: sandboxMode ? 'private' : visibility,
        edit_policy: editPolicy,
        organisation_id: orgId || null
      });
      await goto(`/collections/${created.slug}`);
    } catch (e) {
      error = errorMessage(e);
      saving = false;
    }
  }
</script>

<svelte:head><title>{t('ncoll.head_title')}</title></svelte:head>

<div class="container">
  <nav class="ui breadcrumb"><a href="/">{t('common.back_to_search')}</a></nav>

  <PageHeader title={t('ncoll.h1')} intro={t('ncoll.intro')} />

  {#if !canWrite}
    <p class="locked ui" role="status">
      {t('ncoll.locked')}
    </p>
  {/if}

  <form class="new-form" onsubmit={submit} aria-label={t('ncoll.h1')}>
    <div class="row">
      <div class="field grow">
        <label class="ui" for="nc-name">{t('common.name')}</label>
        <input
          id="nc-name"
          class="input"
          type="text"
          bind:value={name}
          disabled={!canWrite || saving}
          placeholder={t('ncoll.name_placeholder')}
          oninput={() => {
            if (!slugTouched) slug = slugify(name);
          }}
          required
        />
      </div>
      <div class="field year">
        <label class="ui" for="nc-year">{t('coll.year_label')} <span class="opt">{t('common.optional_paren')}</span></label>
        <input id="nc-year" class="input" type="number" bind:value={year} disabled={!canWrite || saving} />
      </div>
    </div>

    <div class="field">
      <label class="ui" for="nc-slug">{t('ncoll.slug_label')} <span class="opt">{t('ncoll.slug_hint')}</span></label>
      <input
        id="nc-slug"
        class="input mono"
        type="text"
        bind:value={slug}
        disabled={!canWrite || saving}
        spellcheck="false"
        oninput={() => (slugTouched = true)}
      />
    </div>

    <div class="field">
      <label class="ui" for="nc-description">{t('coll.description_label')} <span class="opt">{t('ncoll.description_opt')}</span></label>
      <textarea
        id="nc-description"
        class="input"
        rows="3"
        bind:value={description}
        disabled={!canWrite || saving}
      ></textarea>
    </div>

    <div class="row">
      <div class="field grow">
        <label class="ui" for="nc-licence-label">{t('coll.licence_label')} <span class="opt">{t('ncoll.description_opt')}</span></label>
        <input
          id="nc-licence-label"
          class="input"
          type="text"
          bind:value={licenceLabel}
          disabled={!canWrite || saving}
          placeholder={t('coll.licence_placeholder')}
        />
      </div>
      <div class="field grow">
        <label class="ui" for="nc-licence-url">{t('coll.licence_url_label')} <span class="opt">{t('ncoll.description_opt')}</span></label>
        <input
          id="nc-licence-url"
          class="input"
          type="url"
          bind:value={licenceUrl}
          disabled={!canWrite || saving}
          placeholder="https://…"
        />
      </div>
    </div>

    <div class="row">
      <div class="field grow">
        <label class="ui" for="nc-org">{t('coll.org_label')}</label>
        <select id="nc-org" class="input" bind:value={orgId} disabled={!canWrite || saving}>
          <option value=""
            >{currentUser.is_super_admin
              ? t('ncoll.no_org_system')
              : t('ncoll.no_org_personal')}</option
          >
          {#each myAdminOrgs as org (org.id)}
            <option value={org.id}>{org.name}</option>
          {/each}
        </select>
      </div>
      {#if !sandboxMode}
        <div class="field grow">
          <label class="ui" for="nc-visibility">{t('coll.visibility_label')}</label>
          <select id="nc-visibility" class="input" bind:value={visibility} disabled={!canWrite || saving}>
            <option value="public">{t('coll.visibility_public_option')}</option>
            <option value="org_private">{t('coll.visibility_org_option')}</option>
          </select>
        </div>
        <div class="field grow">
          <label class="ui" for="nc-policy">{t('coll.policy_label')}</label>
          <select
            id="nc-policy"
            class="input"
            bind:value={editPolicy}
            disabled={!canWrite || saving}
            title={t('coll.policy_hint')}
          >
            <option value="org">{t('coll.policy_org')}</option>
            <option value="anyone">{t('coll.policy_anyone')}</option>
          </select>
        </div>
      {/if}
    </div>

    {#if sandboxMode}
      <p class="hint ui sandbox-note" role="note">
        {t('ncoll.sandbox_note')}
      </p>
    {:else if visibility === 'org_private' && !orgId}
      <p class="hint ui">
        {t('ncoll.org_hint')}
      </p>
    {/if}

    {#if error}
      <p class="error ui" role="alert">{t('ncoll.create_failed', { error })}</p>
    {/if}

    <div class="actions ui">
      <button type="submit" class="btn btn-primary" disabled={!canWrite || saving}>
        {saving ? t('common.creating') : t('ncoll.create')}
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
    min-width: 220px;
  }

  .year {
    width: 130px;
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

  input,
  textarea,
  select {
    width: 100%;
  }

  /* .input (later in app.css) would otherwise beat the .mono utility. */
  input.mono {
    font-family: var(--font-mono);
  }

  textarea {
    resize: vertical;
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin-bottom: var(--space-4);
  }

  /* Trattcopyn (beslut 2): transparent up front — ingen dark pattern. */
  .sandbox-note {
    max-width: 60ch;
    font-size: var(--text-sm);
    color: var(--ink-2);
    padding: var(--space-3) var(--space-4);
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
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
