/** Creator feedback: types + text helpers for the retention screen. */

export interface RetentionCurve {
  video_id: number;
  duration_ms: number;
  age_s: number;
  views: number;
  histogram: number[]; // 10 buckets of 10% watch ratio
  retention: number[]; // 11 points: share of views reaching >= k*10%
  completion_rate: number;
  avg_watch_ratio: number;
  biggest_drop: { at_pct: number; lost_share: number } | null;
}

export interface MyVideo {
  video_id: number;
  creator_id: number | null;
  url: string | null;
  duration_ms: number;
  created_at: number;
  views: number;
  completion_rate: number;
  avg_watch_ratio: number;
}

export const pct = (x: number) => `${Math.round(x * 100)}%`;

export function dropText(c: RetentionCurve): string {
  if (!c.biggest_drop) return 'No drop-off yet';
  const { at_pct, lost_share } = c.biggest_drop;
  return `${pct(lost_share)} of viewers left between ${at_pct}% and ${at_pct + 10}%`;
}

export function ageText(c: RetentionCurve): string {
  const minutes = Math.floor(c.age_s / 60);
  if (minutes < 1) return 'uploaded just now';
  if (minutes < 60) return `uploaded ${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `uploaded ${hours} h ago`;
  return `uploaded ${Math.floor(hours / 24)} d ago`;
}
