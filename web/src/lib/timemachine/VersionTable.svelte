<script lang="ts">
  import type { VersionOut } from '$lib/api';
  import AuthorLink from '$lib/components/AuthorLink.svelte';
  import { formatDate, statusLabel, t, type TranslationKey } from '$lib/i18n.svelte';

  interface Props {
    versions: VersionOut[];
    stepTypes: (string | null)[];
    focusIndex: number;
    onJump: (index: number) => void;
  }

  let { versions, stepTypes, focusIndex, onJump }: Props = $props();

  const STEP_KEYS: Record<string, TranslationKey> = {
    revised_from: 'vt.step_revised',
    branched_from: 'vt.step_branched',
    synthesized_from: 'vt.step_synthesized',
    translated_from: 'vt.step_translated',
    promoted_from: 'vt.step_promoted'
  };

  function stepLabel(step: string | null): string {
    const key = STEP_KEYS[step ?? ''];
    return key ? t(key) : t('typo.dash');
  }
</script>

<details class="vtable ui">
  <summary>{t('vt.summary', { count: versions.length })}</summary>
  <div class="scroll">
    <table>
      <thead>
        <tr>
          <th scope="col">{t('vt.nr')}</th>
          <th scope="col">{t('vt.date')}</th>
          <th scope="col">{t('vt.name')}</th>
          <th scope="col">{t('vt.author')}</th>
          <th scope="col">{t('common.status')}</th>
          <th scope="col">{t('vt.change_type')}</th>
          <th scope="col">{t('vt.why')}</th>
        </tr>
      </thead>
      <tbody>
        {#each versions as version, i (version.id)}
          <tr class:focus={i === focusIndex}>
            <td>
              <button class="btn btn-quiet jump" onclick={() => onJump(i)}>
                {i + 1}
              </button>
            </td>
            <td class="mono">{formatDate(version.created_at, { dateStyle: 'medium' })}</td>
            <td>{version.canonical_form}</td>
            <td
              ><AuthorLink user={version.created_by} fallback={t('typo.dash')} />{#if version.provenance?.kind === 'llm'}
                <span class="mono ai">AI</span>{/if}</td
            >
            <td>{statusLabel(version.status)}</td>
            <td>{i === 0 ? t('vt.origin') : stepLabel(stepTypes[i])}</td>
            <td class="note">{version.note ?? ''}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</details>

<style>
  .vtable {
    margin-top: var(--space-8);
    font-size: var(--text-sm);
  }

  summary {
    cursor: pointer;
    color: var(--ink-2);
    padding: var(--space-2) 0;
  }

  .scroll {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: var(--space-3);
  }

  th,
  td {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--line);
    vertical-align: top;
  }

  th {
    font-weight: 600;
    color: var(--ink-3);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  tr.focus {
    background: var(--accent-soft);
  }

  .jump {
    padding: 0.2em 0.6em;
    font-family: var(--font-mono);
  }

  .note {
    max-width: 30ch;
    color: var(--ink-2);
    font-style: italic;
  }

  .ai {
    color: var(--accent);
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
    padding: 0 0.3em;
    margin-left: 0.4em;
    font-size: var(--text-2xs);
  }
</style>
