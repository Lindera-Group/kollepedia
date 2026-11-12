/** Central mapping from API errors to localized user-facing messages
 * (plan NG_ATTRIBUTION_OCH_FELHANTERING, paket E2).
 *
 * The server's `detail.message` is English log text and must never be
 * rendered. Known codes map to `apierr.<code>` keys; anything else falls
 * back to localized generic copy per status class, so no raw backend
 * string ever reaches the user regardless of language. */
import { ApiError } from '$lib/api';
import { t, type TranslationKey } from '$lib/i18n.svelte';
import { sv } from '$lib/i18n/sv';

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code) {
      const key = `apierr.${e.code}`;
      if (key in sv) return t(key as TranslationKey, e.params);
    }
    if (e.status >= 500) return t('apierr.fallback_5xx');
    return t('apierr.fallback_4xx', { status: e.status });
  }
  // fetch() network failures surface as TypeError ("Failed to fetch").
  if (e instanceof TypeError) return t('apierr.fallback_network');
  return t('apierr.fallback_unknown');
}
