/** UI language: Swedish (default) + English. UI chrome only — authored
 * content (definitions, the /manual body, /about) stays in its source
 * language. Persisted; mirrored onto <html lang> for a11y.
 *
 * The dictionaries live in ./i18n/sv.ts (key source of truth) and
 * ./i18n/en.ts (typed against the sv key union — parity is a type error).
 * Components must call t()/formatDate() in templates or deriveds so the
 * `i18n.lang` read is tracked and the UI re-renders on switch. */
import { sv, type TranslationKey } from './i18n/sv';
import { en } from './i18n/en';

export type { TranslationKey };

export type Lang = 'sv' | 'en';

const KEY = 'kollepedia-lang';

const dictionaries: Record<Lang, Record<TranslationKey, string>> = { sv, en };

/** Read the language cookie. This is the source of truth *the server can see*,
 * so SSR renders in the visitor's language and there is no hydration mismatch
 * (in particular for {@html} content, which Svelte does not re-render on
 * hydration). */
function readCookie(): Lang | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)kollepedia-lang=(sv|en)\b/);
  return (match?.[1] as Lang | undefined) ?? null;
}

function writeCookie(lang: Lang): void {
  if (typeof document === 'undefined') return;
  // A year, site-wide; Lax so it rides normal navigations (incl. the SSR load).
  document.cookie = `${KEY}=${lang}; path=/; max-age=31536000; SameSite=Lax`;
}

function initial(): Lang {
  const fromCookie = readCookie();
  if (fromCookie) return fromCookie;
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === 'sv' || stored === 'en') return stored;
  } catch {
    /* private mode / non-browser */
  }
  return 'sv';
}

export const i18n = $state<{ lang: Lang }>({ lang: initial() });

// <html lang> must match the restored choice from the very first paint.
if (typeof document !== 'undefined') {
  document.documentElement.lang = i18n.lang;
  // Migrate a legacy localStorage-only preference into the cookie so the next
  // SSR renders the right language (removes the one-time first-load flash).
  if (!readCookie()) writeCookie(i18n.lang);
}

export function setLang(lang: Lang): void {
  i18n.lang = lang;
  if (typeof document !== 'undefined') document.documentElement.lang = lang;
  writeCookie(lang);
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* private mode */
  }
}

/** SSR-only: set the language for the current server render from the request
 * cookie, without touching document/localStorage (absent on the server). The
 * root layout calls this synchronously before children render, so t() and the
 * content-by-language modules resolve in the visitor's language. Safe despite
 * the shared module state: SvelteKit renders a request's tree synchronously,
 * with no await between this call and the reads. */
export function setLangForRender(lang: Lang): void {
  i18n.lang = lang;
}

/** Translate a key in the current language, interpolating {param} tokens. */
export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  let text: string = dictionaries[i18n.lang][key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

const LOCALES: Record<Lang, string> = { sv: 'sv-SE', en: 'en-GB' };

/** Locale-aware date formatting following the UI language (sv-SE / en-GB). */
export function formatDate(iso: string, opts?: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleDateString(
    LOCALES[i18n.lang],
    opts ?? { year: 'numeric', month: 'long', day: 'numeric' }
  );
}

/** Locale-aware number formatting (thousands separators). */
export function formatNumber(value: number): string {
  return value.toLocaleString(LOCALES[i18n.lang]);
}

/** Version-status label ('utkast'/'draft' …); unknown statuses pass through. */
export function statusLabel(status: string): string {
  const key = `status.${status}` as TranslationKey;
  return key in sv ? t(key) : status;
}

/** Content-language label ('svenska'/'Swedish' …); unknown codes pass through. */
export function languageLabel(code: string): string {
  const key = `language.${code}` as TranslationKey;
  return key in sv ? t(key) : code;
}
