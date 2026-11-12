/** BYOK AI settings: the user's personal LLM key + provider choice, stored
 * ONLY in this browser (localStorage). The key is sent per-request via the
 * X-LLM-Key header and proxied by the server without being persisted or
 * logged (VISION §5.1). Iteration 4 adds provider/model/base-URL alongside the
 * key — the same storage slot migrates transparently from the old bare-key
 * value. */

const KEY = 'kollepedia-llm-key';

export type AiProvider = 'anthropic' | 'berget' | 'openai';

export interface AiSettingsValue {
  key: string;
  provider: AiProvider;
  /** Empty string ⇒ the provider default (DEFAULT_MODELS) is used. */
  model: string;
  /** Only honoured for the OpenAI-compatible provider (custom base URL). */
  baseUrl: string;
}

/** Placeholder/default model per provider (roadmap: `body.model` always wins). */
export const DEFAULT_MODELS: Record<AiProvider, string> = {
  anthropic: 'claude-sonnet-5',
  berget: 'meta-llama/Llama-3.3-70B-Instruct',
  openai: 'gpt-4o-mini'
};

const PROVIDERS: readonly AiProvider[] = ['anthropic', 'berget', 'openai'];

function emptySettings(): AiSettingsValue {
  return { key: '', provider: 'anthropic', model: '', baseUrl: '' };
}

/** Parse whatever sits in localStorage. Three shapes are tolerated:
 * - null/'' → empty settings,
 * - a JSON object (iteration 4 format) → validated field by field,
 * - anything else → the legacy bare Anthropic key (pre-night-4). */
export function parseStoredSettings(raw: string | null): AiSettingsValue {
  const out = emptySettings();
  if (!raw) return out;
  if (raw.trimStart().startsWith('{')) {
    try {
      const parsed = JSON.parse(raw) as Partial<Record<keyof AiSettingsValue, unknown>>;
      if (typeof parsed.key === 'string') out.key = parsed.key;
      if (PROVIDERS.includes(parsed.provider as AiProvider)) {
        out.provider = parsed.provider as AiProvider;
      }
      if (typeof parsed.model === 'string') out.model = parsed.model;
      if (typeof parsed.baseUrl === 'string') out.baseUrl = parsed.baseUrl;
      return out;
    } catch {
      /* fall through — treat as a bare key */
    }
  }
  // Legacy migration: the old store held the bare Anthropic key as-is.
  out.key = raw.trim();
  return out;
}

/** The model to send in the request body: explicit choice or provider default. */
export function effectiveModel(settings: Pick<AiSettingsValue, 'provider' | 'model'>): string {
  return settings.model.trim() || DEFAULT_MODELS[settings.provider];
}

/** Base-URL override header value, or undefined when the default applies. */
export function effectiveBaseUrl(
  settings: Pick<AiSettingsValue, 'provider' | 'baseUrl'>
): string | undefined {
  if (settings.provider !== 'openai') return undefined;
  const url = settings.baseUrl.trim();
  return url || undefined;
}

function initial(): AiSettingsValue {
  try {
    return parseStoredSettings(localStorage.getItem(KEY));
  } catch {
    return emptySettings();
  }
}

export const aiSettings = $state<AiSettingsValue>(initial());

function persist(): void {
  try {
    const { key, provider, model, baseUrl } = aiSettings;
    if (!key && provider === 'anthropic' && !model && !baseUrl) {
      localStorage.removeItem(KEY);
    } else {
      localStorage.setItem(KEY, JSON.stringify({ key, provider, model, baseUrl }));
    }
  } catch {
    /* private mode */
  }
}

export function setAiSettings(patch: Partial<AiSettingsValue>): void {
  if (patch.key !== undefined) aiSettings.key = patch.key.trim();
  if (patch.provider !== undefined) aiSettings.provider = patch.provider;
  if (patch.model !== undefined) aiSettings.model = patch.model.trim();
  if (patch.baseUrl !== undefined) aiSettings.baseUrl = patch.baseUrl.trim();
  persist();
}

export function clearAiSettings(): void {
  Object.assign(aiSettings, emptySettings());
  persist();
}
