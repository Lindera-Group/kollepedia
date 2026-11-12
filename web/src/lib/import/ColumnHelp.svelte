<script lang="ts">
  import { t } from '$lib/i18n.svelte';
  import { IMPORT_COLUMNS } from './columns';
</script>

<details class="card colhelp ui">
  <summary>{t('import.colhelp_summary')}</summary>
  <p class="intro">
    {t('import.colhelp_intro_1')}
    <code>,</code> {t('import.colhelp_or')} <code>;</code>
    {t('import.colhelp_intro_2')}
  </p>
  <div class="tablewrap">
    <table>
      <thead>
        <tr>
          <th scope="col">{t('import.col_column')}</th>
          <th scope="col">{t('import.col_required')}</th>
          <th scope="col">{t('import.col_description')}</th>
          <th scope="col">{t('import.col_example')}</th>
        </tr>
      </thead>
      <tbody>
        {#each IMPORT_COLUMNS as column (column.name)}
          <tr>
            <td class="mono">{column.name}</td>
            <td>
              {#if column.required}
                <span class="req">{t('import.required')}</span>
              {:else}
                <span class="opt">{t('import.optional')}</span>
              {/if}
            </td>
            <td>{t(column.descriptionKey)}</td>
            <td class="mono example">{column.example}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</details>

<style>
  .colhelp {
    margin-top: var(--space-6);
    padding: var(--space-4) var(--space-6);
    font-size: var(--text-sm);
  }

  summary {
    cursor: pointer;
    font-weight: 600;
    padding: var(--space-2) 0;
  }

  summary:hover {
    color: var(--accent);
  }

  .intro {
    color: var(--ink-2);
    max-width: 75ch;
    margin-top: var(--space-3);
  }

  code {
    font-family: var(--font-mono);
    background: var(--bg-sunken);
    padding: 0 0.3em;
    border-radius: var(--radius-sm);
  }

  .tablewrap {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 640px;
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .req {
    color: var(--del-strong);
    font-weight: 600;
  }

  .opt {
    color: var(--ink-3);
  }

  .example {
    color: var(--ink-3);
    max-width: 22ch;
  }
</style>
