/** Event batcher: queue client events, POST them every 5 s and whenever the app goes to background. */

export type EventKind = 'impression' | 'watch' | 'swipe' | 'rewatch' | 'share' | 'save' | 'pause';

export interface ClientEvent {
  video_id: number;
  kind: EventKind;
  watch_ms?: number;
  position?: number;
  ts?: number; // epoch seconds
}

export interface TrailItem {
  id: number;
  kind: 'saved' | 'series_progress' | 'topic_unlocked' | 'streak' | string;
  ref_id: number | null;
  payload: Record<string, unknown> | null;
  session_id: string;
  ts: number;
}

export interface IngestResult {
  accepted: number;
  trail: TrailItem[];
}

export type Sender = (events: ClientEvent[]) => Promise<IngestResult>;

export interface BatcherOptions {
  send: Sender;
  intervalMs?: number;
  maxQueue?: number;
  onTrail?: (items: TrailItem[]) => void;
}

export const FLUSH_INTERVAL_MS = 5000;

export class EventBatcher {
  private queue: ClientEvent[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private flushing = false;
  private readonly intervalMs: number;
  private readonly maxQueue: number;

  constructor(private readonly opts: BatcherOptions) {
    this.intervalMs = opts.intervalMs ?? FLUSH_INTERVAL_MS;
    this.maxQueue = opts.maxQueue ?? 500;
  }

  get size(): number {
    return this.queue.length;
  }

  peek(): readonly ClientEvent[] {
    return this.queue;
  }

  add(event: ClientEvent): void {
    this.queue.push({ ts: Date.now() / 1000, ...event });
    this.trim();
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.flush(), this.intervalMs);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /** Send everything queued now. Safe to call from AppState changes and on unmount. */
  async flush(): Promise<void> {
    if (this.flushing || this.queue.length === 0) return;
    this.flushing = true;
    const batch = this.queue.splice(0, this.queue.length);
    try {
      const result = await this.opts.send(batch);
      if (result?.trail?.length) this.opts.onTrail?.(result.trail);
    } catch {
      this.queue.unshift(...batch); // keep for the next tick
      this.trim();
    } finally {
      this.flushing = false;
    }
  }

  private trim(): void {
    if (this.queue.length > this.maxQueue) this.queue.splice(0, this.queue.length - this.maxQueue);
  }
}
