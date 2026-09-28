"""Redis adapters: profile decay on read, session window and TTL. Uses fakeredis."""
from __future__ import annotations

import fakeredis
import pytest

from api.stores import SESSION_TTL_S, ProfileStore, SessionStore
from engine.models import Event, UserProfile

DAY = 24 * 3600
NOW = 1_800_000_000.0


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def ev(video_id: int, ratio: float, topic: str = "cooking", kind: str = "watch") -> Event:
    return Event(video_id=video_id, kind=kind, watch_ratio=ratio, topics={topic: 1.0}, ts=NOW)


class TestProfileStore:
    def test_unknown_user_is_an_empty_profile(self, r):
        p = ProfileStore(r).load(1)
        assert p.topics == {} and p.seen == set() and p.series_progress == {}

    def test_apply_persists_topics_and_seen(self, r):
        store = ProfileStore(r)
        store.apply(1, ev(10, 1.0), now=NOW)
        p = store.load(1)
        assert p.topics["cooking"] > 0 and p.seen == {10} and p.last_update_ts == NOW

    def test_seven_day_half_life_is_applied_on_read(self, r):
        store = ProfileStore(r)
        store.apply(1, ev(10, 1.0), now=NOW)
        w0 = store.topics(1, now=NOW)["cooking"]
        w7 = store.topics(1, now=NOW + 7 * DAY)["cooking"]
        w14 = store.topics(1, now=NOW + 14 * DAY)["cooking"]
        assert w7 == pytest.approx(w0 / 2) and w14 == pytest.approx(w0 / 4)
        assert float(r.hget("user:1:topics", "cooking")) == pytest.approx(w0), "stored weight is raw; decay is read-time"

    def test_decay_is_folded_in_before_a_new_event(self, r):
        store = ProfileStore(r)
        store.apply(1, ev(10, 1.0), now=NOW)
        store.apply(1, ev(11, 1.0, topic="art"), now=NOW + 7 * DAY)
        p = store.load(1)
        assert p.topics["cooking"] == pytest.approx(p.topics["art"] / 2)
        assert p.last_update_ts == NOW + 7 * DAY

    def test_series_progress_and_topic_unlock(self, r):
        store = ProfileStore(r)
        store.set_series_progress(1, series_id=5, index=2)
        assert store.load(1).series_progress == {5: 2}
        assert store.unlock_topic(1, "cooking") is True
        assert store.unlock_topic(1, "cooking") is False

    def test_load_matches_engine_profile_semantics(self, r):
        store = ProfileStore(r)
        ref = UserProfile(user_id=1, last_update_ts=NOW)
        for i, ratio in enumerate([1.0, 0.2, 0.9]):
            ref.apply(ev(i, ratio), now=NOW + i)
            store.apply(1, ev(i, ratio), now=NOW + i)
        got = store.load(1)
        assert got.topics["cooking"] == pytest.approx(ref.topics["cooking"]) and got.seen == ref.seen


class TestSessionStore:
    def test_unknown_session_is_empty(self, r):
        s = SessionStore(r).load("abc")
        assert s.events == [] and s.served == set()

    def test_keeps_last_20_events_in_order(self, r):
        store = SessionStore(r)
        for i in range(25):
            store.push("abc", ev(i, 0.5))
        s = store.load("abc")
        assert [e.video_id for e in s.events] == list(range(5, 25))

    def test_event_fields_round_trip(self, r):
        store = SessionStore(r)
        e = Event(video_id=3, kind="swipe", watch_ratio=0.12, topics={"news": 1.0, "__sentiment__": -0.6}, ts=NOW)
        store.push("abc", e)
        assert store.load("abc").events[0] == e

    def test_served_ids_and_ttl(self, r):
        store = SessionStore(r)
        store.add_served("abc", [1, 2, 3])
        store.push("abc", ev(1, 0.5))
        assert store.load("abc").served == {1, 2, 3}
        assert SESSION_TTL_S - 5 < r.ttl("session:abc:served") <= SESSION_TTL_S
        assert SESSION_TTL_S - 5 < r.ttl("session:abc:events") <= SESSION_TTL_S
        assert SESSION_TTL_S == 30 * 60
