/** Session id: one per app run, renewed after 30 min in the background (the server's session TTL). */

export const SESSION_IDLE_MS = 30 * 60 * 1000;

type Listener = (id: string) => void;

export class SessionManager {
  private current: string;
  private backgroundedAt: number | null = null;
  private readonly listeners = new Set<Listener>();
  private readonly now: () => number;

  constructor(private readonly opts: { newId: () => string; now?: () => number }) {
    this.now = opts.now ?? Date.now;
    this.current = opts.newId();
  }

  get id(): string {
    return this.current;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  onAppState(state: string): void {
    if (state === 'active') {
      if (this.backgroundedAt !== null && this.now() - this.backgroundedAt > SESSION_IDLE_MS) this.renew();
      this.backgroundedAt = null;
    } else if (state === 'background' || state === 'inactive') {
      this.backgroundedAt ??= this.now();
    }
  }

  renew(): void {
    this.current = this.opts.newId();
    this.listeners.forEach((fn) => fn(this.current));
  }
}
