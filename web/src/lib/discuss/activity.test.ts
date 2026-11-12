import { describe, expect, it } from 'vitest';
import { activityIconFilled, activityIconName, groupByDay } from './activity';
import { ICONS } from '$lib/icons/icons';

describe('groupByDay', () => {
  it('groups consecutive items on the same calendar day, preserving order', () => {
    const items = [
      { at: '2026-07-04T14:30:00', id: 'a' },
      { at: '2026-07-04T09:00:00', id: 'b' },
      { at: '2026-07-03T23:59:59', id: 'c' },
      { at: '2026-07-01T08:00:00', id: 'd' }
    ];
    const groups = groupByDay(items);
    expect(groups.map((g) => g.day)).toEqual(['2026-07-04', '2026-07-03', '2026-07-01']);
    expect(groups[0].items.map((i) => i.id)).toEqual(['a', 'b']);
    expect(groups[2].items.map((i) => i.id)).toEqual(['d']);
  });

  it('returns an empty list for an empty feed', () => {
    expect(groupByDay([])).toEqual([]);
  });
});

describe('activityIconName', () => {
  it('maps every known kind to an icon that exists in the library', () => {
    const kinds = [
      'version',
      'endorsement',
      'comment',
      'proposal',
      'proposal_merged',
      'proposal_rejected',
      'proposal_withdrawn',
      'branch',
      'merge'
    ];
    for (const kind of kinds) {
      expect(ICONS[activityIconName(kind)]).toBeDefined();
    }
  });

  it('falls back to the neutral pulse for unknown kinds', () => {
    expect(activityIconName('mystery')).toBe('pulse');
  });

  it('renders endorsements filled (gold star), everything else outline', () => {
    expect(activityIconFilled('endorsement')).toBe(true);
    expect(activityIconFilled('version')).toBe(false);
  });
});
