<script lang="ts">
  import type { ImportResult } from '$lib/api';
  import { t } from '$lib/i18n.svelte';

  let { result }: { result: ImportResult } = $props();
</script>

<div class="report ui" role="status" aria-live="polite">
  <p class="summary">
    {#if result.dry_run}
      <strong>{t('import.dry_run')}</strong> {t('import.nothing_saved')}
    {:else}
      <strong>{t('import.done')}</strong>
    {/if}
    {t('import.rows_read', { count: result.rows_total })} ·
    <span class="ok">{result.created} {result.dry_run ? t('import.would_create') : t('import.created')}</span>
    {#if result.errors.length}
      · <span class="bad">{t('import.errors_count', { count: result.errors.length })}</span>
    {/if}
    {#if result.warnings.length}
      · <span class="warn">{t('import.warnings_count', { count: result.warnings.length })}</span>
    {/if}
  </p>

  {#if result.errors.length}
    <div class="tablewrap">
      <table>
        <caption class="mono">{t('import.errors_caption')}</caption>
        <thead>
          <tr><th scope="col">{t('import.row')}</th><th scope="col">{t('import.message')}</th></tr>
        </thead>
        <tbody>
          {#each result.errors as error (error.row + error.message)}
            <tr>
              <td class="mono">{error.row}</td>
              <td>{error.message}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if result.warnings.length}
    <ul class="warnings">
      {#each result.warnings as warning (warning)}
        <li>{warning}</li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .report {
    margin-top: var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-sunken);
    padding: var(--space-4);
    font-size: var(--text-sm);
  }

  .summary {
    margin: 0;
  }

  .ok {
    color: var(--ins-strong);
    font-weight: 600;
  }

  .bad {
    color: var(--del-strong);
    font-weight: 600;
  }

  .warn {
    color: var(--endorsed);
    font-weight: 600;
  }

  .tablewrap {
    overflow-x: auto;
    margin-top: var(--space-3);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
  }

  caption {
    text-align: left;
    padding: var(--space-2) 0;
    color: var(--ink-3);
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  th:first-child,
  td:first-child {
    width: 4rem;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .warnings {
    margin: var(--space-3) 0 0;
    padding-left: 1.2em;
    color: var(--endorsed);
  }

  .warnings li {
    margin-bottom: var(--space-1);
  }
</style>
