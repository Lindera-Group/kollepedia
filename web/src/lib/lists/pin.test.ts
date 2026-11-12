import { describe, expect, it } from 'vitest';
import { sv } from '$lib/i18n/sv';
import { pinLabel, shortId } from './pin';

describe('shortId', () => {
  it('truncates to eight characters and tolerates null', () => {
    expect(shortId('abcdef12-3456-7890')).toBe('abcdef12');
    expect(shortId(null)).toBe('');
    expect(shortId(undefined)).toBe('');
  });
});

describe('pinLabel', () => {
  it('labels a pinned item with its short version id', () => {
    expect(pinLabel({ version_id: 'deadbeef-cafe', follow_head: false })).toBe(
      sv['pin.pinned_at'].replace('{id}', 'deadbeef')
    );
  });

  it('labels follow-head items as following latest', () => {
    expect(pinLabel({ version_id: 'deadbeef-cafe', follow_head: true })).toBe(sv['pin.follows']);
    expect(pinLabel({ version_id: null, follow_head: false })).toBe(sv['pin.follows']);
  });
});
