import { describe, expect, it } from 'vitest';
import * as Y from 'yjs';
import { PEER_PALETTE, collabParams, collabServerUrl, peerColor, shouldSeed } from './helpers';

/** WCAG 2.1 relative luminance + contrast ratio (the peer palette promises
 * ≥ 4.5:1 against the white chip/cursor-label text). */
function srgbChannel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function contrastVsWhite(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const luminance =
    0.2126 * srgbChannel((n >> 16) & 255) +
    0.7152 * srgbChannel((n >> 8) & 255) +
    0.0722 * srgbChannel(n & 255);
  return 1.05 / (luminance + 0.05);
}

describe('peerColor', () => {
  it('maps a name deterministically into the 8-colour palette', () => {
    expect(PEER_PALETTE).toHaveLength(8);
    expect(new Set(PEER_PALETTE).size).toBe(8);
    for (const name of ['martin', 'Åsa Öberg', 'x', '', 'medredigerare-42']) {
      expect(peerColor(name)).toBe(peerColor(name));
      expect(PEER_PALETTE).toContain(peerColor(name));
    }
    // Distinct names spread across hues rather than collapsing onto one.
    const hues = new Set(Array.from({ length: 24 }, (_, i) => peerColor(`user-${i}`)));
    expect(hues.size).toBeGreaterThan(4);
  });

  it('keeps every palette colour at WCAG AA (≥ 4.5:1) against white text', () => {
    for (const color of PEER_PALETTE) {
      expect(contrastVsWhite(color), color).toBeGreaterThanOrEqual(4.5);
    }
  });
});

describe('shouldSeed', () => {
  it('seeds only while the shared fields map is empty (first peer)', () => {
    const doc = new Y.Doc();
    const fields = doc.getMap<string>('fields');
    expect(shouldSeed(fields)).toBe(true);
    fields.set('base_version_id', 'v1');
    expect(shouldSeed(fields)).toBe(false);
    doc.destroy();
  });
});

describe('collab ws URL', () => {
  it('derives ws/wss from the page protocol', () => {
    expect(collabServerUrl({ protocol: 'http:', host: 'localhost:5181' })).toBe(
      'ws://localhost:5181/ws/collab'
    );
    expect(collabServerUrl({ protocol: 'https:', host: 'kollepedia.example' })).toBe(
      'wss://kollepedia.example/ws/collab'
    );
  });

  it('prefers the JWT over the dev handle, and sends nothing anonymously', () => {
    expect(collabParams({ token: 'jwt-abc', handle: 'martin' })).toEqual({ token: 'jwt-abc' });
    expect(collabParams({ token: null, handle: 'martin' })).toEqual({ who: 'martin' });
    expect(collabParams({ token: null, handle: '   ' })).toEqual({});
    expect(collabParams({ token: null, handle: '' })).toEqual({});
  });
});
