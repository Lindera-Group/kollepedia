/** Theme cycling: light → dark → contrast. Persisted; applied to <html data-theme>. */

const THEMES = ['light', 'dark', 'contrast'] as const;
export type Theme = (typeof THEMES)[number];

const KEY = 'kollepedia-theme';

function initial(): Theme {
  if (typeof document === 'undefined') return 'light';
  const current = document.documentElement.dataset.theme;
  return THEMES.includes(current as Theme) ? (current as Theme) : 'light';
}

export const theme = $state<{ current: Theme }>({ current: initial() });

export function cycleTheme(): void {
  const next = THEMES[(THEMES.indexOf(theme.current) + 1) % THEMES.length];
  theme.current = next;
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* private mode */
  }
}

// Theme display names are translated via i18n keys 'theme.light' | 'theme.dark'
// | 'theme.contrast' (see $lib/i18n) — the old themeLabels export is gone.
