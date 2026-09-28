/** Prefetch the next videos into the cache directory so the next swipe starts instantly. */
import { Directory, File, Paths } from 'expo-file-system';
import { Platform } from 'react-native';

const inflight = new Map<number, Promise<void>>();
const MAX_CACHED = 24;

function cacheDir(): Directory | null {
  if (Platform.OS === 'web') return null;
  try {
    const dir = new Directory(Paths.cache, 'vibo-videos');
    if (!dir.exists) dir.create();
    return dir;
  } catch {
    return null;
  }
}

/** Local file uri if this video is already cached, else null. */
export function localUri(videoId: number): string | null {
  const dir = cacheDir();
  if (!dir) return null;
  try {
    const f = new File(dir, `${videoId}.mp4`);
    return f.exists ? f.uri : null;
  } catch {
    return null;
  }
}

export function prefetch(videos: { video_id: number; url: string }[]): void {
  const dir = cacheDir();
  if (!dir) return;
  for (const v of videos) {
    if (inflight.has(v.video_id) || localUri(v.video_id)) continue;
    const task = File.downloadFileAsync(v.url, new File(dir, `${v.video_id}.mp4`))
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => inflight.delete(v.video_id));
    inflight.set(v.video_id, task);
  }
}

/** Keep the cache small: drop files that are not in `keep` once we're over the cap. */
export function trimCache(keep: Set<number>): void {
  const dir = cacheDir();
  if (!dir) return;
  try {
    const files = dir.list().filter((f): f is File => f instanceof File);
    if (files.length <= MAX_CACHED) return;
    for (const f of files) {
      const id = Number(f.name.replace('.mp4', ''));
      if (!keep.has(id)) f.delete();
    }
  } catch {
    /* cache is best-effort */
  }
}
