import { describe, expect, it } from '@jest/globals';

import { ageText, dropText, type RetentionCurve } from '../creator';

const curve = (over: Partial<RetentionCurve> = {}): RetentionCurve => ({
  video_id: 1,
  duration_ms: 10000,
  age_s: 0,
  views: 7,
  histogram: [1, 2, 0, 0, 0, 1, 0, 0, 0, 3],
  retention: [1, 6 / 7, 4 / 7, 4 / 7, 4 / 7, 4 / 7, 3 / 7, 3 / 7, 3 / 7, 3 / 7, 3 / 7],
  completion_rate: 3 / 7,
  avg_watch_ratio: 0.6,
  biggest_drop: { at_pct: 10, lost_share: 2 / 7 },
  ...over,
});

describe('dropText', () => {
  it('names the segment where most viewers left', () => {
    expect(dropText(curve())).toBe('29% of viewers left between 10% and 20%');
  });
  it('says so when nobody left yet', () => {
    expect(dropText(curve({ biggest_drop: null }))).toBe('No drop-off yet');
  });
});

describe('ageText', () => {
  it('formats minutes, hours and days since upload', () => {
    expect(ageText(curve({ age_s: 90 }))).toBe('uploaded 1 min ago');
    expect(ageText(curve({ age_s: 3 * 3600 + 5 }))).toBe('uploaded 3 h ago');
    expect(ageText(curve({ age_s: 2 * 86400 }))).toBe('uploaded 2 d ago');
  });
});
