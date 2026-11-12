<script lang="ts">
  import type { ProposalOut } from '$lib/api';
  import { t, type TranslationKey } from '$lib/i18n.svelte';

  interface Props {
    status: ProposalOut['status'];
  }

  let { status }: Props = $props();

  const KEYS: Record<ProposalOut['status'], TranslationKey> = {
    open: 'prop.status_open',
    merged: 'prop.status_merged',
    rejected: 'prop.status_rejected',
    withdrawn: 'prop.status_withdrawn'
  };
</script>

<span class="pill st-{status}">{t(KEYS[status])}</span>

<style>
  .st-open {
    border-color: var(--accent);
    color: var(--accent);
  }

  .st-merged {
    border-color: var(--ins-strong);
    color: var(--ins-strong);
  }

  .st-rejected {
    border-color: var(--del-strong);
    color: var(--del-strong);
  }

  .st-withdrawn {
    color: var(--ink-3);
    border-style: dashed;
  }
</style>
