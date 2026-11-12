/** Pure helpers for list items' pin semantics (VISION §3: pinned by default). */
import { t } from '$lib/i18n.svelte';

/** First 8 characters of a version id — enough to recognise, short enough to scan. */
export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : '';
}

/** Localised pin-status label for a list item. */
export function pinLabel(item: { version_id: string | null; follow_head: boolean }): string {
  if (item.follow_head || !item.version_id) return t('pin.follows');
  return t('pin.pinned_at', { id: shortId(item.version_id) });
}
