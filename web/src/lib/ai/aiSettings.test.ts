import { describe, expect, it } from 'vitest';
import {
  DEFAULT_MODELS,
  effectiveBaseUrl,
  effectiveModel,
  parseStoredSettings
} from './aiKey.svelte';

describe('parseStoredSettings (night-4 migration)', () => {
  it('migrates the legacy bare Anthropic key to full settings', () => {
    expect(parseStoredSettings('sk-ant-abc123')).toEqual({
      key: 'sk-ant-abc123',
      provider: 'anthropic',
      model: '',
      baseUrl: ''
    });
  });

  it('returns empty settings for null/empty storage', () => {
    expect(parseStoredSettings(null)).toEqual({
      key: '',
      provider: 'anthropic',
      model: '',
      baseUrl: ''
    });
    expect(parseStoredSettings('')).toEqual({
      key: '',
      provider: 'anthropic',
      model: '',
      baseUrl: ''
    });
  });

  it('round-trips the JSON format and validates the provider', () => {
    const stored = JSON.stringify({
      key: 'sk-x',
      provider: 'berget',
      model: 'meta-llama/Llama-3.3-70B-Instruct',
      baseUrl: ''
    });
    expect(parseStoredSettings(stored)).toEqual({
      key: 'sk-x',
      provider: 'berget',
      model: 'meta-llama/Llama-3.3-70B-Instruct',
      baseUrl: ''
    });
    // Unknown provider falls back to anthropic instead of poisoning requests.
    const bad = JSON.stringify({ key: 'sk-y', provider: 'evil', model: '', baseUrl: '' });
    expect(parseStoredSettings(bad).provider).toBe('anthropic');
  });

  it('treats malformed JSON-ish values as a bare key', () => {
    expect(parseStoredSettings('{not json').key).toBe('{not json');
  });
});

describe('effectiveModel / effectiveBaseUrl', () => {
  it('falls back to the provider default model when none is set', () => {
    expect(effectiveModel({ provider: 'berget', model: '' })).toBe(DEFAULT_MODELS.berget);
    expect(effectiveModel({ provider: 'anthropic', model: '  ' })).toBe(DEFAULT_MODELS.anthropic);
    expect(effectiveModel({ provider: 'openai', model: 'gpt-4.1' })).toBe('gpt-4.1');
  });

  it('only honours the base URL for the OpenAI-compatible provider', () => {
    expect(effectiveBaseUrl({ provider: 'openai', baseUrl: 'https://llm.example/v1' })).toBe(
      'https://llm.example/v1'
    );
    expect(effectiveBaseUrl({ provider: 'openai', baseUrl: '' })).toBeUndefined();
    expect(effectiveBaseUrl({ provider: 'berget', baseUrl: 'https://x' })).toBeUndefined();
    expect(effectiveBaseUrl({ provider: 'anthropic', baseUrl: 'https://x' })).toBeUndefined();
  });
});
