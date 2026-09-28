/** Human strings. Centralized so translation (Hebrew, RTL) is a single-file change later. */
import type { TrailItem } from './events';
import type { FeedVideo } from './feed';

export const strings = {
  appName: 'VIBO',
  trail: 'Trail',
  feedEmpty: 'Nothing more for now. Come back later.',
  feedError: 'Could not reach the server. Pull down to retry.',
  chapterTitle: (n: number) => `Chapter ${n} done`,
  chapterEmpty: 'Nothing saved yet. Watch to the end or save something to leave a trail.',
  keepGoing: 'Keep going',
  seeTrail: 'See your trail',
  save: 'Save',
  saved: 'Saved',
  share: 'Share',
  more: 'More',
  stats: 'Stats: where people leave',
  myVideos: 'My videos',
  report: 'Report',
  blockCreator: 'Block creator',
  cancel: 'Cancel',
  reportTitle: 'Report this video',
  reportDone: 'Thanks. You will not see this video again, and we will review it.',
  blockDone: 'Creator blocked. Their videos will not appear in your feed.',
  trailEmpty: 'Your trail is empty. Everything you finish, save or unlock lands here.',
  consentTitle: 'Before you start',
  consentBody:
    'VIBO shows short videos made by other people. There is no place here for harassment, hate, sexual content, ' +
    'violence or spam. You can report any video and block any creator, and we act on reports within 24 hours.\n\n' +
    'We only use what you do inside the app (what you watch, skip, save) to rank your feed. No location, no ' +
    'contacts, no advertising identifiers.',
  consentAgree: 'I agree',
};

export const reportReasons: { key: 'spam' | 'harassment' | 'violence' | 'sexual' | 'misinformation' | 'other'; label: string }[] = [
  { key: 'spam', label: 'Spam or misleading' },
  { key: 'harassment', label: 'Harassment or hate' },
  { key: 'violence', label: 'Violence' },
  { key: 'sexual', label: 'Sexual content' },
  { key: 'misinformation', label: 'False information' },
  { key: 'other', label: 'Something else' },
];

export function trailLabel(t: TrailItem): string {
  const p = (t.payload ?? {}) as Record<string, any>;
  switch (t.kind) {
    case 'saved':
      return `Saved video #${t.ref_id}`;
    case 'series_progress':
      return `Series ${t.ref_id} · episode ${(p.index ?? 0) + 1}`;
    case 'topic_unlocked':
      return `Unlocked topic: ${p.topic}`;
    case 'streak':
      return `Finished ${p.completions ?? 0} video${p.completions === 1 ? '' : 's'} this session`;
    default:
      return t.kind;
  }
}

/** Why is this video here? Straight from the ranker's breakdown, so the feed stays explainable. */
export function whyLabel(v: FeedVideo): string {
  if (v.slot === 'series') return 'Next episode of a series you started';
  if (v.slot === 'explore') return 'Something outside your usual';
  if (v.slot === 'probe') return 'Getting to know you';
  const b = v.breakdown ?? {};
  const top = (['affinity', 'cohort', 'quality', 'fresh', 'cold_start'] as const)
    .map((k) => [k, b[k] ?? 0] as const)
    .sort((a, c) => c[1] - a[1])[0];
  const topic = mainTopic(v);
  switch (top?.[0]) {
    case 'affinity':
      return `Because you watch ${topic}`;
    case 'cohort':
      return `People like you watch ${topic}`;
    case 'quality':
      return 'People finish this one';
    case 'fresh':
      return 'Just uploaded';
    case 'cold_start':
      return 'New creator, first views';
    default:
      return topic;
  }
}

export function mainTopic(v: FeedVideo): string {
  const entries = Object.entries(v.topics ?? {});
  if (!entries.length) return '';
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}
