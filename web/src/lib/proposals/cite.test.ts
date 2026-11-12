import { describe, expect, it } from 'vitest';
import { formatCitation, shortId } from './cite';

describe('shortId', () => {
  it('takes the first 8 characters of a version id', () => {
    expect(shortId('a1b2c3d4-e5f6-7890-abcd-ef0123456789')).toBe('a1b2c3d4');
    expect(shortId('abc')).toBe('abc');
  });
});

describe('formatCitation', () => {
  it('produces the full citation line with the 8-char version id', () => {
    expect(
      formatCitation({
        author: 'Karin Berg',
        canonicalForm: 'hållplats',
        collection: 'Kollektivtrafikordboken',
        versionId: 'a1b2c3d4-e5f6-7890-abcd-ef0123456789',
        date: '4 juli 2026',
        dash: '–',
        url: 'https://kollepedia.example/versions/a1b2c3d4-e5f6-7890-abcd-ef0123456789'
      })
    ).toBe(
      "Karin Berg, 'hållplats', Kollektivtrafikordboken – version a1b2c3d4, 4 juli 2026. " +
        'https://kollepedia.example/versions/a1b2c3d4-e5f6-7890-abcd-ef0123456789'
    );
  });
});
