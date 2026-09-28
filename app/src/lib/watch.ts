/** Tracks how long a video actually played and turns that into the event the server expects. */
import type { ClientEvent, EventKind } from './events';

export type LeaveEvent = Pick<ClientEvent, 'kind' | 'watch_ms' | 'position'>;

export class WatchTracker {
  private accumulated = 0;
  private playingSince: number | null = null;

  constructor(private readonly durationMs: number, private readonly now: () => number = Date.now) {}

  setPlaying(playing: boolean): void {
    const t = this.now();
    if (playing && this.playingSince === null) this.playingSince = t;
    else if (!playing && this.playingSince !== null) {
      this.accumulated += t - this.playingSince;
      this.playingSince = null;
    }
  }

  get watchedMs(): number {
    return this.accumulated + (this.playingSince === null ? 0 : this.now() - this.playingSince);
  }

  /** The user moved on: swipe (<50%), watch, or rewatch (>100%, loops). */
  leave(position: number): LeaveEvent {
    const ms = this.watchedMs;
    const ratio = ms / Math.max(1, this.durationMs);
    const kind: EventKind = ratio < 0.5 ? 'swipe' : ratio > 1 ? 'rewatch' : 'watch';
    return { kind, watch_ms: Math.round(ms), position };
  }

  action(kind: Extract<EventKind, 'save' | 'share' | 'pause'>, position: number): LeaveEvent {
    return { kind, watch_ms: Math.round(this.watchedMs), position };
  }
}
