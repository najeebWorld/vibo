import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import { SESSION_IDLE_MS, SessionManager } from '../session';

describe('SessionManager', () => {
  const make = (now: () => number) => {
    const ids = ['a', 'b', 'c'];
    return new SessionManager({ newId: () => ids.shift()!, now });
  };

  it('keeps one id while the app is active', () => {
    const s = make(() => 0);
    expect(s.id).toBe('a');
    expect(s.id).toBe('a');
  });

  it('renews the id after 30 minutes in the background (matches the server TTL)', () => {
    let t = 0;
    const s = make(() => t);
    s.onAppState('background');
    t = SESSION_IDLE_MS + 1;
    s.onAppState('active');
    expect(s.id).toBe('b');
    expect(SESSION_IDLE_MS).toBe(30 * 60 * 1000);
  });

  it('does not renew after a short background', () => {
    let t = 0;
    const s = make(() => t);
    s.onAppState('background');
    t = 5 * 60 * 1000;
    s.onAppState('active');
    expect(s.id).toBe('a');
  });

  it('notifies listeners when the session changes', () => {
    let t = 0;
    const s = make(() => t);
    const seen: string[] = [];
    s.subscribe((id) => seen.push(id));
    s.onAppState('background');
    t = SESSION_IDLE_MS + 1;
    s.onAppState('active');
    expect(seen).toEqual(['b']);
  });
});
