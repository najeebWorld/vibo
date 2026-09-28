import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import { WatchTracker } from '../watch';

describe('WatchTracker', () => {
  it('accumulates only the time the video was actually playing', () => {
    let t = 0;
    const w = new WatchTracker(10000, () => t);
    w.setPlaying(true);
    t = 3000;
    w.setPlaying(false);
    t = 9000;
    w.setPlaying(true);
    t = 10000;
    expect(w.watchedMs).toBe(4000);
  });

  it('classifies an early leave as a swipe', () => {
    let t = 0;
    const w = new WatchTracker(10000, () => t);
    w.setPlaying(true);
    t = 2000;
    expect(w.leave(3)).toEqual({ kind: 'swipe', watch_ms: 2000, position: 3 });
  });

  it('classifies most of the video as a watch and more than the whole as a rewatch', () => {
    let t = 0;
    const w = new WatchTracker(10000, () => t);
    w.setPlaying(true);
    t = 7000;
    expect(w.leave(0).kind).toBe('watch');
    t = 12000;
    expect(w.leave(0).kind).toBe('rewatch');
  });

  it('counts a save on top of the watch', () => {
    const w = new WatchTracker(10000, () => 0);
    expect(w.action('save', 2)).toEqual({ kind: 'save', watch_ms: 0, position: 2 });
  });
});
