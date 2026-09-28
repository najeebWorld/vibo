import { API_URL } from './config';
import type { MyVideo, RetentionCurve } from './creator';
import type { ClientEvent, IngestResult, TrailItem } from './events';
import type { FeedVideo } from './feed';

export type ReportReason = 'spam' | 'harassment' | 'violence' | 'sexual' | 'misinformation' | 'other';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, { ...init, headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) } });
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  register: (device_id: string) => post<{ user_id: number }>('/users', { device_id }),

  feed: (user_id: string, session_id: string, n = 8) =>
    request<{ user_id: number; items: FeedVideo[] }>(
      `/feed?user_id=${encodeURIComponent(user_id)}&session_id=${session_id}&n=${n}`,
    ),

  events: (user_id: string, session_id: string, events: ClientEvent[]) =>
    post<IngestResult>('/events', { user_id, session_id, events }),

  trail: (user_id: string, session_id?: string) =>
    request<{ items: TrailItem[] }>(
      `/me/trail?user_id=${encodeURIComponent(user_id)}&limit=200${session_id ? `&session_id=${session_id}` : ''}`,
    ),

  report: (video_id: number, user_id: string, reason: ReportReason) =>
    post<{ hidden: boolean }>(`/videos/${video_id}/report`, { user_id, reason }),

  block: (user_id: string, blocked_user_id: number) => post<{ ok: boolean }>('/users/block', { user_id, blocked_user_id }),

  retention: (video_id: number) => request<RetentionCurve>(`/videos/${video_id}/retention`),

  myVideos: (user_id: string) => request<{ user_id: number; items: MyVideo[] }>(`/me/videos?user_id=${encodeURIComponent(user_id)}`),

  health: () => request<{ ok: boolean }>('/health'),
};
