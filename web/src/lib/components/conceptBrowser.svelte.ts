/** The shared concept-browse engine (Bengt deep-review #1): one accumulating
 * infinite-scroll list with debounced filter resets, a sequence token that
 * invalidates in-flight responses, and snapshot capture/restore for
 * history-back position memory.
 *
 * Extracted verbatim from the twin implementations in routes/+page.svelte and
 * routes/collections/[slug]/+page.svelte — the pages keep their own param
 * shapes and $effect wiring; this class owns the state machine.
 *
 * scrollY note (from the originals): SvelteKit's native scroll restoration is
 * insufficient with Svelte 5's batched DOM swap — kit reads the outgoing
 * scroll position after the (shorter) destination page is in the DOM, so the
 * browser has clamped scrollY. capture() runs while the page is fully alive;
 * the page re-applies scrollY one frame after restore. */
import type { ConceptListItem } from '$lib/api';
import { appendPage, hasMore, nextOffset, PAGE_LIMIT } from './infiniteList';

export interface BrowserPage {
  items: ConceptListItem[];
  total: number;
}

export interface BrowserSnapshot<P> {
  params: P | null;
  items: ConceptListItem[];
  offset: number;
  total: number | null;
}

export interface BrowserOptions<P> {
  fetchPage: (params: P, offset: number, limit: number) => Promise<BrowserPage>;
  /** Equality over the page's param shape — a match skips the refetch (this
   * is what keeps accumulated pages alive right after a snapshot restore). */
  sameParams: (a: P, b: P) => boolean;
  /** Blocks the sentinel for param states that must not paginate (e.g. the
   * collection page's client-side multi-tag narrowing). Default: allow. */
  canLoadMore?: (params: P) => boolean;
  seed?: { params: P; page: BrowserPage } | null;
}

export class ConceptBrowser<P> {
  items = $state<ConceptListItem[]>([]);
  total = $state<number | null>(null);
  offset = $state(0);
  searching = $state(false);
  loadingMore = $state(false);
  /** Consumed by InfiniteSentinel's no-retrigger guard after a restore. */
  restoredFromSnapshot = $state(false);

  /** The params the accumulated items belong to. */
  active: P | null = null;

  #seq = 0;
  #timer: ReturnType<typeof setTimeout> | undefined;
  readonly #opts: BrowserOptions<P>;

  constructor(opts: BrowserOptions<P>) {
    this.#opts = opts;
    if (opts.seed) {
      this.items = opts.seed.page.items;
      this.total = opts.seed.page.total;
      this.offset = nextOffset(0, opts.seed.page.items.length, opts.seed.page.total);
      this.active = opts.seed.params;
    }
  }

  /** The debounced filter reset — call from the page's $effect with fresh
   * params. `immediate` renders a pre-fetched page (SSR seed) without a
   * network roundtrip; `debounceMs` 0 fires at once. */
  reset(
    params: P,
    options: { debounceMs?: number; immediate?: BrowserPage | null; limit?: number } = {}
  ): void {
    clearTimeout(this.#timer);
    if (this.active !== null && this.#opts.sameParams(this.active, params)) return;
    this.#seq++;
    const mySeq = this.#seq;
    this.loadingMore = false;
    if (options.immediate) {
      this.items = options.immediate.items;
      this.total = options.immediate.total;
      this.offset = nextOffset(0, options.immediate.items.length, options.immediate.total);
      this.active = params;
      this.searching = false;
      return;
    }
    this.searching = true;
    this.#timer = setTimeout(async () => {
      try {
        const page = await this.#opts.fetchPage(params, 0, options.limit ?? PAGE_LIMIT);
        if (mySeq !== this.#seq) return;
        this.items = page.items;
        this.total = page.total;
        this.offset = nextOffset(0, page.items.length, page.total);
        this.active = params;
      } catch {
        /* transient — the next filter change or retry refetches */
      } finally {
        if (mySeq === this.#seq) this.searching = false;
      }
    }, options.debounceMs ?? 0);
  }

  async loadMore(): Promise<void> {
    const params = this.active;
    if (
      !params ||
      this.loadingMore ||
      this.searching ||
      !hasMore(this.offset, this.total) ||
      !(this.#opts.canLoadMore?.(params) ?? true)
    ) {
      return;
    }
    const mySeq = this.#seq;
    this.loadingMore = true;
    try {
      const page = await this.#opts.fetchPage(params, this.offset, PAGE_LIMIT);
      if (mySeq !== this.#seq) return;
      this.items = appendPage(this.items, page.items);
      this.offset = nextOffset(this.offset, page.items.length, page.total);
      this.total = page.total;
    } catch {
      /* transient — the next sentinel crossing retries */
    } finally {
      this.loadingMore = false;
    }
  }

  /** The list half of the page's Snapshot — pages add their own filter state. */
  capture(): BrowserSnapshot<P> {
    return {
      params: this.active,
      items: $state.snapshot(this.items) as ConceptListItem[],
      offset: this.offset,
      total: this.total
    };
  }

  restore(snapshot: BrowserSnapshot<P>): void {
    this.active = snapshot.params;
    this.items = snapshot.items;
    this.offset = snapshot.offset;
    this.total = snapshot.total;
    this.restoredFromSnapshot = true;
  }
}
