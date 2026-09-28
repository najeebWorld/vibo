import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import { EventBatcher, type ClientEvent, type Sender } from '../events';

const sender = () => jest.fn<Sender>();

const ev = (video_id: number, kind: ClientEvent['kind'] = 'watch'): ClientEvent => ({ video_id, kind, watch_ms: 5000, position: 0 });

describe('EventBatcher', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('posts the queue every 5 seconds', async () => {
    const send = sender().mockResolvedValue({ accepted: 2, trail: [] });
    const b = new EventBatcher({ send, intervalMs: 5000 });
    b.start();
    b.add(ev(1));
    b.add(ev(2));
    expect(send).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(5000);
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toHaveLength(2);
    b.stop();
  });

  it('does not post when the queue is empty', async () => {
    const send = sender().mockResolvedValue({ accepted: 0, trail: [] });
    const b = new EventBatcher({ send, intervalMs: 5000 });
    b.start();
    await jest.advanceTimersByTimeAsync(15000);
    expect(send).not.toHaveBeenCalled();
    b.stop();
  });

  it('flushes immediately on demand (app going to background)', async () => {
    const send = sender().mockResolvedValue({ accepted: 1, trail: [] });
    const b = new EventBatcher({ send, intervalMs: 5000 });
    b.add(ev(1));
    await b.flush();
    expect(send).toHaveBeenCalledTimes(1);
    expect(b.size).toBe(0);
  });

  it('keeps events for retry when the post fails', async () => {
    const send = sender().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ accepted: 1, trail: [] });
    const b = new EventBatcher({ send, intervalMs: 5000 });
    b.add(ev(1));
    await b.flush();
    expect(b.size).toBe(1);
    await b.flush();
    expect(b.size).toBe(0);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('reports trail entries returned by the server', async () => {
    const trail = [{ id: 1, kind: 'streak', ref_id: null, payload: { completions: 1 }, session_id: 's', ts: 0 }];
    const send = sender().mockResolvedValue({ accepted: 1, trail });
    const onTrail = jest.fn<(items: unknown[]) => void>();
    const b = new EventBatcher({ send, intervalMs: 5000, onTrail });
    b.add(ev(1));
    await b.flush();
    expect(onTrail).toHaveBeenCalledWith(trail);
  });

  it('drops the oldest events past the cap', () => {
    const b = new EventBatcher({ send: sender(), intervalMs: 5000, maxQueue: 3 });
    [1, 2, 3, 4].forEach((i) => b.add(ev(i)));
    expect(b.size).toBe(3);
    expect(b.peek().map((e) => e.video_id)).toEqual([2, 3, 4]);
  });
});
