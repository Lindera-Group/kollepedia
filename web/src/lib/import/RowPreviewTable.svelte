<script lang="ts">
  import type { ImportRow } from '$lib/api';
  import Icon from '$lib/icons/Icon.svelte';
  import { t } from '$lib/i18n.svelte';

  let {
    rows,
    onedit
  }: {
    rows: ImportRow[];
    onedit?: () => void;
  } = $props();

  function removeRow(index: number): void {
    rows.splice(index, 1);
    onedit?.();
  }

  function extras(row: ImportRow): string {
    const parts: string[] = [];
    if (row.status) parts.push(`status: ${row.status}`);
    if (row.variants) parts.push(`${t('import.extras_variants')}: ${row.variants}`);
    if (row.related_to) parts.push(`${t('import.extras_related')}: ${row.related_to}`);
    if (row.broader) parts.push(`${t('import.extras_broader')}: ${row.broader}`);
    if (row.narrower) parts.push(`${t('import.extras_narrower')}: ${row.narrower}`);
    if (row.translation_of) parts.push(`${t('import.extras_translation_of')}: ${row.translation_of}`);
    if (row.source) parts.push(`${t('import.extras_source')}: ${row.source}`);
    return parts.join(' · ');
  }
</script>

<div class="tablewrap ui">
  <table>
    <caption class="mono">
      {t('import.preview_caption', { count: rows.length })}
    </caption>
    <thead>
      <tr>
        <th scope="col" class="numcol">#</th>
        <th scope="col">{t('import.th_term')}</th>
        <th scope="col">{t('import.th_language')}</th>
        <th scope="col">{t('import.th_definition')}</th>
        <th scope="col">{t('import.th_tags')}</th>
        <th scope="col" class="delcol"><span class="sr-only">{t('import.th_remove_sr')}</span></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row, index (index)}
        <tr>
          <td class="mono numcol">{index + 1}</td>
          <td>
            <input
              class="input cell-input"
              type="text"
              bind:value={row.canonical_form}
              oninput={onedit}
              aria-label={t('import.aria_canonical_row', { row: index + 1 })}
            />
          </td>
          <td>
            <select
              class="input cell-input"
              bind:value={row.language}
              onchange={onedit}
              aria-label={t('import.aria_language_row', { row: index + 1 })}
            >
              <option value={undefined}>{t('import.sv_default_option')}</option>
              <option value="sv">sv</option>
              <option value="en">en</option>
            </select>
          </td>
          <td class="defcol">
            <textarea
              class="input cell-input"
              rows="2"
              bind:value={row.definition}
              oninput={onedit}
              aria-label={t('import.aria_definition_row', { row: index + 1 })}
            ></textarea>
          </td>
          <td>
            <input
              class="input cell-input"
              type="text"
              bind:value={row.tags}
              oninput={onedit}
              placeholder="tagg1;tagg2"
              aria-label={t('import.aria_tags_row', { row: index + 1 })}
            />
          </td>
          <td class="delcol">
            <button
              type="button"
              class="btn btn-quiet del"
              onclick={() => removeRow(index)}
              aria-label={t('import.aria_remove_row', {
                row: index + 1,
                name: row.canonical_form || t('import.no_term')
              })}
              title={t('import.remove_row_title')}
            >
              <Icon name="close" size={14} />
            </button>
          </td>
        </tr>
        {#if extras(row)}
          <tr class="extras">
            <td></td>
            <td colspan="5" class="mono">{extras(row)}</td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>

<style>
  .tablewrap {
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 720px;
    font-size: var(--text-sm);
  }

  caption {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    color: var(--ink-3);
    border-bottom: 1px solid var(--line);
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2) var(--space-2);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .numcol {
    width: 2.5rem;
    color: var(--ink-3);
  }

  .delcol {
    width: 3rem;
    text-align: center;
  }

  .defcol {
    min-width: 240px;
  }

  /* Dense preview table — compact composition on top of the .input primitive. */
  .cell-input {
    width: 100%;
    padding: 0.35em 0.5em;
    border-radius: var(--radius-sm);
  }

  textarea {
    resize: vertical;
    font-family: var(--font-serif);
    line-height: 1.4;
  }

  .del {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.35em;
    color: var(--del-strong);
    padding: 0.2em 0.55em;
  }

  .del:hover {
    background: var(--del-wash);
    color: var(--del-strong);
  }

  .extras td {
    color: var(--ink-3);
    padding-top: 0;
    border-bottom: 1px solid var(--line);
  }

</style>
