import { describe, expect, it } from 'vitest';
import { featuresFromEnv, NO_FEATURES } from './features';

describe('featuresFromEnv', () => {
  it('is dark by default', () => {
    expect(featuresFromEnv({})).toEqual(NO_FEATURES);
    expect(featuresFromEnv({ FEATURE_AI: '0' }).ai).toBe(false);
    expect(featuresFromEnv({ FEATURE_AI: 'nej' }).ai).toBe(false);
  });

  it('accepts the usual truthy spellings', () => {
    for (const value of ['1', 'true', 'YES', ' on ']) {
      expect(featuresFromEnv({ FEATURE_AI: value }).ai, value).toBe(true);
    }
  });
});
