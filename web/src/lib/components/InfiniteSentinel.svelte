<script lang="ts">
  import { formatNumber, t } from '$lib/i18n.svelte';

  let {
    count,
    total,
    hasMore,
    loading = false,
    skipFirst = false,
    onLoadMore
  }: {
    /** Rendered item count — each append re-arms the observer, whose fresh
     * initial observation chains loads until the viewport is filled. */
    count: number;
    total: number;
    hasMore: boolean;
    loading?: boolean;
    /** Snapshot-restore guard: swallow the observer's first intersecting
     * observation so a history-back landing at the bottom of the restored
     * list does not immediately fetch another page. */
    skipFirst?: boolean;
    onLoadMore: () => void;
  } = $props();

  let sentinel = $state<HTMLDivElement | undefined>();
  // No-retrigger guard, captured ONCE at component init — intentionally not
  // reactive: the page's snapshot restore() runs before render, so a
  // history-back mount sees true. Two layers: (1) arming waits two frames so
  // the observer's first measurement sees the RESTORED scroll position (the
  // page's restore re-applies scrollY in a rAF that runs within the FIRST
  // frame; this component's script runs before restore(), so a single rAF
  // here would measure too early); (2) `skip` swallows that first
  // observation — intersecting or not — so a restore landing at the list
  // bottom does not immediately fetch. Both are consumed on first use and
  // normal loading resumes.
  // svelte-ignore state_referenced_locally
  const skipInitial = skipFirst;
  let skip = skipInitial;
  let armed = $state(!skipInitial);
  if (skipInitial) {
    requestAnimationFrame(() => requestAnimationFrame(() => (armed = true)));
  }

  // Browser-only by construction ($effect never runs during SSR) and
  // disconnected on teardown/re-arm.
  $effect(() => {
    const el = sentinel;
    void count; // reactive dep: re-arm after every append
    if (!el || !hasMore || !armed) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (!entry.isIntersecting || skip) {
          skip = false;
          return;
        }
        if (!loading) onLoadMore();
      },
      { rootMargin: '320px 0px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  });
</script>

<div class="foot ui">
  <div class="sentinel" bind:this={sentinel} aria-hidden="true"></div>
  <div class="load-row">
    {#if loading}<span class="spinner" aria-hidden="true"></span>{/if}
    <span class="sr-only" aria-live="polite">{loading ? t('inf.loading_more') : ''}</span>
  </div>
  <p class="counter mono" aria-live="polite">
    {t('inf.counter', { count: formatNumber(count), total: formatNumber(total) })}
  </p>
</div>

<style>
  .foot {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-6);
  }

  .sentinel {
    width: 100%;
    height: 1px;
  }

  /* Fixed height whether or not the spinner shows — no layout jump. */
  .load-row {
    display: flex;
    align-items: center;
    min-height: 1.4em;
  }

  .counter {
    font-size: var(--text-xs);
    color: var(--ink-3);
    margin: 0;
  }

  .spinner {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    border: 2px solid var(--line);
    border-top-color: var(--accent);
    border-radius: var(--radius-round);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

</style>
