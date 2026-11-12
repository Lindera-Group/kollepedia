<script lang="ts">
  import { t } from '$lib/i18n.svelte';
  import Icon from '$lib/icons/Icon.svelte';
  import {
    aiSettings,
    clearAiSettings,
    DEFAULT_MODELS,
    setAiSettings,
    type AiProvider
  } from './aiKey.svelte';

  let open = $state(false);
  let keyInput = $state('');
  let provider = $state<AiProvider>('anthropic');
  let model = $state('');
  let baseUrl = $state('');
  let justSaved = $state(false);

  let root = $state<HTMLElement | undefined>();
  let trigger = $state<HTMLButtonElement | undefined>();

  const PROVIDER_OPTIONS: { value: AiProvider; labelKey: 'aiprov.provider_anthropic' | 'aiprov.provider_berget' | 'aiprov.provider_openai' }[] = [
    { value: 'anthropic', labelKey: 'aiprov.provider_anthropic' },
    { value: 'berget', labelKey: 'aiprov.provider_berget' },
    { value: 'openai', labelKey: 'aiprov.provider_openai' }
  ];

  const KEY_PLACEHOLDERS: Record<AiProvider, string> = {
    anthropic: 'sk-ant-…',
    berget: 'sk-…',
    openai: 'sk-…'
  };

  function toggle(): void {
    if (open) {
      close();
      return;
    }
    keyInput = aiSettings.key;
    provider = aiSettings.provider;
    model = aiSettings.model;
    baseUrl = aiSettings.baseUrl;
    justSaved = false;
    open = true;
  }

  function close(): void {
    open = false;
    trigger?.focus();
  }

  function save(): void {
    setAiSettings({ key: keyInput, provider, model, baseUrl });
    justSaved = true;
  }

  function clear(): void {
    clearAiSettings();
    keyInput = '';
    provider = 'anthropic';
    model = '';
    baseUrl = '';
    justSaved = false;
  }

  function onWindowPointerDown(event: PointerEvent): void {
    if (!open) return;
    if (root && event.target instanceof Node && !root.contains(event.target)) open = false;
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (open && event.key === 'Escape') {
      event.preventDefault();
      close();
    }
  }

  function focusOnMount(node: HTMLElement): void {
    node.focus();
  }
</script>

<svelte:window onpointerdown={onWindowPointerDown} onkeydown={onWindowKeydown} />

<div class="aisettings ui" bind:this={root}>
  <button
    class="btn btn-quiet"
    bind:this={trigger}
    onclick={toggle}
    aria-haspopup="dialog"
    aria-expanded={open}
  >
    <span class="dot" class:active={!!aiSettings.key} aria-hidden="true"></span>
    {t('aiprov.button')}
    {#if aiSettings.key}<span class="mono state">{t('ai.active')}</span>{/if}
  </button>

  {#if open}
    <div class="pop card" role="dialog" aria-label={t('aiprov.dialog_aria')}>
      <label class="field">
        <span>{t('aiprov.provider_label')}</span>
        <select class="input" bind:value={provider} use:focusOnMount>
          {#each PROVIDER_OPTIONS as option (option.value)}
            <option value={option.value}>{t(option.labelKey)}</option>
          {/each}
        </select>
      </label>

      <label class="field">
        <span>{t('aiprov.model_label')}</span>
        <input
          class="input"
          type="text"
          bind:value={model}
          placeholder={DEFAULT_MODELS[provider]}
          autocomplete="off"
          spellcheck="false"
        />
      </label>
      {#if provider === 'berget'}
        <p class="fine">{t('aiprov.model_hint_berget')}</p>
      {/if}

      {#if provider === 'openai'}
        <label class="field">
          <span>{t('aiprov.base_url_label')}</span>
          <input
            class="input"
            type="url"
            bind:value={baseUrl}
            placeholder="https://api.openai.com/v1"
            autocomplete="off"
            spellcheck="false"
          />
        </label>
      {/if}

      <label class="field">
        <span>{t('aiprov.key_label')}</span>
        <input
          class="input"
          type="password"
          bind:value={keyInput}
          placeholder={KEY_PLACEHOLDERS[provider]}
          autocomplete="off"
        />
      </label>

      <div class="row">
        <button class="btn btn-primary" onclick={save} disabled={!keyInput.trim()}>{t('common.save')}</button>
        {#if aiSettings.key}
          <button class="btn" onclick={clear}>{t('common.clear')}</button>
        {/if}
        <button class="btn btn-quiet" onclick={close}>{t('common.close')}</button>
      </div>

      {#if justSaved}
        <p class="saved" role="status"><Icon name="check" size={14} /> {t('aiprov.saved')}</p>
      {/if}

      <p class="fine">
        {t('aiprov.custody_note')}
      </p>
      <p class="fine mono">{t('ai.byok_note')}</p>
    </div>
  {/if}
</div>

<style>
  .aisettings {
    position: relative;
    display: inline-block;
  }

  .dot {
    display: inline-block;
    width: 0.5em;
    height: 0.5em;
    margin-right: 0.35em;
    border-radius: var(--radius-round);
    background: var(--line);
    vertical-align: 0.08em;
  }

  .dot.active {
    background: var(--ins-strong);
  }

  .state {
    margin-left: 0.4em;
    color: var(--ins-strong);
  }

  .pop {
    position: absolute;
    top: calc(100% + var(--space-2));
    right: 0;
    z-index: 60;
    width: min(360px, 86vw);
    padding: var(--space-4);
    box-shadow: var(--shadow-md);
    font-size: var(--text-sm);
  }

  .field {
    display: block;
    margin-bottom: var(--space-3);
  }

  .field span {
    display: block;
    margin-bottom: var(--space-1);
    font-weight: 600;
  }

  .field input,
  .field select {
    width: 100%;
  }

  .field input {
    font-family: var(--font-mono);
  }

  .row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }

  .saved {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    margin: 0 0 var(--space-2);
    color: var(--ins-strong);
  }

  .fine {
    margin: 0 0 var(--space-2);
    font-size: var(--text-xs);
    color: var(--ink-3);
    line-height: 1.5;
  }

  .fine:last-child {
    margin-bottom: 0;
  }
</style>
