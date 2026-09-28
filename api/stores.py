"""Redis adapters that map to/from the engine's UserProfile and SessionState.

Keys
  user:{id}:topics   hash  topic -> raw weight, plus __ts__ (epoch of last write). Decay is applied on read.
  user:{id}:seen     set   video ids the user has already been served/watched
  user:{id}:series   hash  series_id -> last index watched
  user:{id}:unlocked set   topics the user has completed at least one video in
  session:{id}:events list last 20 events as JSON, chronological, TTL 30 min
  session:{id}:served set  video ids served in this session, TTL 30 min
"""
from __future__ import annotations

import json
import time

import redis

from engine.models import Event, SessionState, UserProfile

SESSION_TTL_S = 30 * 60
TS_FIELD = "__ts__"


class ProfileStore:
    def __init__(self, r: redis.Redis):
        self.r = r

    @staticmethod
    def _k(user_id: int, part: str) -> str:
        return f"user:{user_id}:{part}"

    def load(self, user_id: int) -> UserProfile:
        pipe = self.r.pipeline()
        pipe.hgetall(self._k(user_id, "topics"))
        pipe.smembers(self._k(user_id, "seen"))
        pipe.hgetall(self._k(user_id, "series"))
        topics, seen, series = pipe.execute()
        ts = float(topics.pop(TS_FIELD, time.time()))
        return UserProfile(
            user_id=user_id,
            topics={t: float(w) for t, w in topics.items()},
            last_update_ts=ts,
            seen={int(v) for v in seen},
            series_progress={int(k): int(v) for k, v in series.items()},
        )

    def topics(self, user_id: int, now: float) -> dict[str, float]:
        """Taste with the 7-day half-life applied as of `now`."""
        return self.load(user_id).decayed_topics(now)

    def apply(self, user_id: int, ev: Event, now: float) -> UserProfile:
        """Fold one event into the profile exactly as engine.models.UserProfile.apply does."""
        p = self.load(user_id)
        p.apply(ev, now)
        pipe = self.r.pipeline()
        key = self._k(user_id, "topics")
        pipe.delete(key)
        pipe.hset(key, mapping={**{t: repr(w) for t, w in p.topics.items()}, TS_FIELD: repr(p.last_update_ts)})
        pipe.sadd(self._k(user_id, "seen"), ev.video_id)
        pipe.execute()
        return p

    def hide(self, user_id: int, video_id: int) -> None:
        """Reported videos never come back: they join the user's seen set."""
        self.r.sadd(self._k(user_id, "seen"), video_id)

    def set_series_progress(self, user_id: int, series_id: int, index: int) -> None:
        self.r.hset(self._k(user_id, "series"), str(series_id), str(index))

    def unlock_topic(self, user_id: int, topic: str) -> bool:
        """True the first time this user completes something in `topic`."""
        return self.r.sadd(self._k(user_id, "unlocked"), topic) == 1


class SessionStore:
    def __init__(self, r: redis.Redis):
        self.r = r

    @staticmethod
    def _k(session_id: str, part: str) -> str:
        return f"session:{session_id}:{part}"

    def load(self, session_id: str) -> SessionState:
        pipe = self.r.pipeline()
        pipe.lrange(self._k(session_id, "events"), 0, -1)
        pipe.smembers(self._k(session_id, "served"))
        raw_events, served = pipe.execute()
        return SessionState(
            session_id=session_id,
            events=[_event_from_json(s) for s in raw_events],
            served={int(v) for v in served},
        )

    def push(self, session_id: str, ev: Event) -> None:
        key = self._k(session_id, "events")
        pipe = self.r.pipeline()
        pipe.rpush(key, _event_to_json(ev))
        pipe.ltrim(key, -SessionState.MAX_EVENTS, -1)
        pipe.expire(key, SESSION_TTL_S)
        pipe.expire(self._k(session_id, "served"), SESSION_TTL_S)
        pipe.execute()

    def add_served(self, session_id: str, video_ids: list[int]) -> None:
        if not video_ids:
            return
        key = self._k(session_id, "served")
        pipe = self.r.pipeline()
        pipe.sadd(key, *video_ids)
        pipe.expire(key, SESSION_TTL_S)
        pipe.expire(self._k(session_id, "events"), SESSION_TTL_S)
        pipe.execute()


def _event_to_json(ev: Event) -> str:
    return json.dumps({"v": ev.video_id, "k": ev.kind, "r": ev.watch_ratio, "t": ev.topics, "ts": ev.ts})


def _event_from_json(s: str) -> Event:
    d = json.loads(s)
    return Event(video_id=d["v"], kind=d["k"], watch_ratio=d["r"], topics=d["t"], ts=d["ts"])
