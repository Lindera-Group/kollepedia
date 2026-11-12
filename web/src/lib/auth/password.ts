import { t } from '$lib/i18n.svelte';

/** Minimum password length for NEW passwords (register, change, reset).
 * Login never length-checks, so existing shorter passwords still work.
 * Keep in sync with the backend (server/app/routers/auth.py). */
export const PASSWORD_MIN_LENGTH = 12;

/** Shared password-form validation (reset flow, iteration 3). Returns a localised
 * error message, or null when the pair is acceptable. */
export function validateNewPassword(password: string, confirmation: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) return t('password.too_short');
  if (password !== confirmation) return t('password.mismatch');
  return null;
}
