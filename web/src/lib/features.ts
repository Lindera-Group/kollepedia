/** Feature flags, read from the web container's environment in the root
 * layout's server load and handed to every page as `page.data.features`.
 * Unfinished functionality ships dark: the server refuses its endpoints and
 * the web hides its UI until the flag is on. Same variable names as
 * server/app/features.py — one `.env` switches both. */

export interface Features {
  /** FEATURE_AI — AI drafts, text extraction and saved prompts. */
  ai: boolean;
}

export const NO_FEATURES: Features = { ai: false };

const ON = new Set(['1', 'true', 'yes', 'on']);

export function featuresFromEnv(env: Record<string, string | undefined>): Features {
  return { ai: ON.has((env.FEATURE_AI ?? '').trim().toLowerCase()) };
}
