/** Pure feed-list logic: chapter cards every 12 videos, refill threshold, de-duplication. */

export interface FeedVideo {
  video_id: number;
  creator_id: number | null;
  url: string;
  duration_ms: number;
  topics: Record<string, number>;
  sentiment: number;
  series_id: number | null;
  series_index: number | null;
  score: number;
  slot: 'exploit' | 'explore' | 'series' | 'probe' | string;
  breakdown: Record<string, number>;
}

export type FeedEntry =
  | { type: 'video'; key: string; video: FeedVideo }
  | { type: 'chapter'; key: string; chapter: number };

export const CHAPTER_EVERY = 12;
export const REFILL_WHEN_LEFT = 3;
export const PAGE_SIZE = 8;

export function interleaveChapters(videos: FeedVideo[]): FeedEntry[] {
  const out: FeedEntry[] = [];
  videos.forEach((video, i) => {
    out.push({ type: 'video', key: `v-${video.video_id}`, video });
    if ((i + 1) % CHAPTER_EVERY === 0) {
      const chapter = (i + 1) / CHAPTER_EVERY;
      out.push({ type: 'chapter', key: `chapter-${chapter}`, chapter });
    }
  });
  return out;
}

/** True when 3 or fewer videos remain after `index` (chapter cards don't count). */
export function needsMore(entries: FeedEntry[], index: number): boolean {
  let left = 0;
  for (let i = index + 1; i < entries.length; i++) if (entries[i].type === 'video') left++;
  return left <= REFILL_WHEN_LEFT;
}

export function mergeVideos(existing: FeedVideo[], incoming: FeedVideo[]): FeedVideo[] {
  const seen = new Set(existing.map((v) => v.video_id));
  return [...existing, ...incoming.filter((v) => !seen.has(v.video_id))];
}

/** The next `count` videos after `index`, for prefetching. */
export function upcomingVideos(entries: FeedEntry[], index: number, count = 3): FeedVideo[] {
  const out: FeedVideo[] = [];
  for (let i = index + 1; i < entries.length && out.length < count; i++) {
    const e = entries[i];
    if (e.type === 'video') out.push(e.video);
  }
  return out;
}
