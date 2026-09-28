import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import { CHAPTER_EVERY, interleaveChapters, mergeVideos, needsMore, type FeedVideo } from '../feed';

const vid = (id: number): FeedVideo => ({
  video_id: id, creator_id: 1, url: `http://x/${id}.mp4`, duration_ms: 10000, topics: { cooking: 1 },
  sentiment: 0, series_id: null, series_index: null, score: 1, slot: 'exploit', breakdown: {},
});
const vids = (n: number) => Array.from({ length: n }, (_, i) => vid(i + 1));

describe('interleaveChapters', () => {
  it('puts a chapter card after every 12 videos', () => {
    expect(CHAPTER_EVERY).toBe(12);
    const entries = interleaveChapters(vids(30));
    const chapterAt = entries.map((e, i) => (e.type === 'chapter' ? i : -1)).filter((i) => i >= 0);
    expect(chapterAt).toEqual([12, 25]);
    expect(entries).toHaveLength(32);
  });

  it('numbers chapters and keeps video order', () => {
    const entries = interleaveChapters(vids(13));
    expect(entries[12]).toEqual({ type: 'chapter', key: 'chapter-1', chapter: 1 });
    expect(entries.filter((e) => e.type === 'video').map((e) => (e as any).video.video_id)).toEqual(vids(13).map((v) => v.video_id));
  });

  it('adds no card for fewer than 12 videos', () => {
    expect(interleaveChapters(vids(11)).every((e) => e.type === 'video')).toBe(true);
  });
});

describe('needsMore', () => {
  it('asks for the next page when 3 or fewer videos remain after the current one', () => {
    const entries = interleaveChapters(vids(8));
    expect(needsMore(entries, 3)).toBe(false);
    expect(needsMore(entries, 4)).toBe(true);
    expect(needsMore(entries, 7)).toBe(true);
  });

  it('ignores chapter cards when counting what is left', () => {
    const entries = interleaveChapters(vids(14)); // chapter at 12
    expect(needsMore(entries, 9)).toBe(false); // videos left: 10..13 = 4
    expect(needsMore(entries, 10)).toBe(true);
  });
});

describe('mergeVideos', () => {
  it('appends new videos and drops ids already in the list', () => {
    const merged = mergeVideos(vids(3), [vid(3), vid(4)]);
    expect(merged.map((v) => v.video_id)).toEqual([1, 2, 3, 4]);
  });
});
