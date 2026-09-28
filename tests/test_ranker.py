"""Behavioral tests for engine/ranker.py. Run: pytest -q

Each test protects one product rule from CLAUDE.md / ARCHITECTURE.md:
  - exploration share is respected (and never below the 0.10 floor)
  - session fatigue lowers a topic after 3 early swipes
  - already-seen items never reappear in the same session
  - mood guard never allows 3 consecutive negative-sentiment items
  - rank() always returns a per-item score breakdown
"""
from __future__ import annotations

import math
import time

import pytest

from engine.models import Event, SessionState, UserProfile, Video
from engine.ranker import EXPLORE_SHARE, MAX_NEGATIVE_RUN, WEIGHTS, rank

NOW = time.time()
NEG = -0.8   # clearly below the -0.3 mood-guard threshold
POS = 0.5
SIGNALS = ("affinity", "quality", "cohort", "fresh", "cold_start", "fatigue", "noise")


# ----------------------------------------------------------------------------- helpers

def vid(i: int, topic: str, sentiment: float = 0.0, impressions: int = 100, completions: int = 60, **kw) -> Video:
    return Video(id=i, topics={topic: 1.0}, duration_ms=10_000, created_ts=NOW,
                 sentiment=sentiment, impressions=impressions, completions=completions, **kw)


def profile(**topics: float) -> UserProfile:
    return UserProfile(user_id=1, topics=topics or {"cooking": 3.0}, last_update_ts=NOW)


def catalog(in_topic: str = "cooking", out_topic: str = "art", n: int = 30) -> list[Video]:
    """n videos inside the user's taste + n outside it."""
    return [vid(i, in_topic) for i in range(n)] + [vid(100 + i, out_topic) for i in range(n)]


def push(session: SessionState, kind: str, ratio: float, topic: str, sentiment: float = 0.0, i: int = 0) -> None:
    topics = {topic: 1.0, "__sentiment__": sentiment}
    session.push(Event(video_id=900 + i, kind=kind, watch_ratio=ratio, topics=topics, ts=NOW))


def swipes(session: SessionState, topic: str, count: int) -> None:
    for i in range(count):
        push(session, "swipe", 0.1, topic, i=i)


def negative_run_lengths(items) -> list[int]:
    runs, run = [], 0
    for s in items:
        run = run + 1 if s.video.sentiment < -0.3 else 0
        runs.append(run)
    return runs


def mean_position(items, topic: str) -> float:
    pos = [i for i, s in enumerate(items) if topic in s.video.topics]
    return sum(pos) / len(pos)


# ----------------------------------------------------------------------------- exploration

class TestExploreShare:
    def test_share_never_below_floor(self):
        assert EXPLORE_SHARE >= 0.10, "CLAUDE.md: EXPLORE_SHARE never drops below 0.10"

    @pytest.mark.parametrize("n", [8, 20])
    def test_explore_slots_match_share(self, n):
        out = rank(profile(), SessionState("s"), catalog(), n=n, now=NOW, seed=0)
        assert len(out) == n
        assert sum(1 for s in out if s.slot == "explore") == max(1, round(n * EXPLORE_SHARE))

    def test_explore_items_are_outside_profile(self):
        out = rank(profile(), SessionState("s"), catalog(), n=8, now=NOW, seed=0)
        explore = [s for s in out if s.slot == "explore"]
        assert explore
        for s in explore:
            assert "art" in s.video.topics
            assert s.breakdown["affinity"] < 0.3 * WEIGHTS["affinity"]

    def test_explore_items_are_spread_not_dumped_at_end(self):
        out = rank(profile(), SessionState("s"), catalog(), n=20, now=NOW, seed=0)
        positions = [i for i, s in enumerate(out) if s.slot == "explore"]
        assert len(positions) == 3
        assert positions[0] < len(out) - 3, positions

    def test_explore_prefers_high_quality_unknowns(self):
        good = vid(200, "art", impressions=100, completions=90)
        bad = [vid(300 + i, "art", impressions=100, completions=10) for i in range(5)]
        vids = [vid(i, "cooking") for i in range(10)] + bad + [good]
        out = rank(profile(), SessionState("s"), vids, n=8, now=NOW, seed=0)
        explore = [s for s in out if s.slot == "explore"]
        assert [s.video.id for s in explore] == [good.id]


# ----------------------------------------------------------------------------- session fatigue

class TestSessionFatigue:
    def test_three_early_swipes_penalize_the_topic(self):
        s = SessionState("s")
        swipes(s, "cooking", 3)
        out = rank(profile(), s, catalog("cooking", "music", n=10), n=20, now=NOW, seed=0)
        cooking = [x for x in out if "cooking" in x.video.topics]
        music = [x for x in out if "music" in x.video.topics]
        assert cooking and music
        assert all(x.breakdown["fatigue"] <= -0.9 for x in cooking)
        assert all(x.breakdown["fatigue"] == 0.0 for x in music)

    def test_fatigue_demotes_the_topic_in_the_ordering(self):
        fresh = rank(profile(), SessionState("a"), catalog("cooking", "music", n=10), n=20, now=NOW, seed=0)
        tired = SessionState("b")
        swipes(tired, "cooking", 3)
        after = rank(profile(), tired, catalog("cooking", "music", n=10), n=20, now=NOW, seed=0)
        assert mean_position(after, "cooking") > mean_position(fresh, "cooking")

    def test_fatigue_grows_with_each_early_swipe(self):
        penalties = []
        for count in (1, 2, 3):
            s = SessionState(f"s{count}")
            swipes(s, "cooking", count)
            out = rank(profile(), s, catalog("cooking", "music", n=5), n=10, now=NOW, seed=0)
            penalties.append(next(x.breakdown["fatigue"] for x in out if x.video.id == 0))
        assert penalties[0] > penalties[1] > penalties[2]

    def test_three_swipes_reach_full_fatigue(self):
        s = SessionState("s")
        swipes(s, "cooking", 1)
        assert s.topic_fatigue()["cooking"] < 0.4
        swipes(s, "cooking", 2)
        assert s.topic_fatigue()["cooking"] >= 0.8

    def test_full_watches_do_not_cause_fatigue(self):
        s = SessionState("s")
        for i in range(3):
            push(s, "watch", 0.95, "cooking", i=i)
        out = rank(profile(), s, catalog("cooking", "music", n=10), n=20, now=NOW, seed=0)
        assert all(x.breakdown["fatigue"] == 0.0 for x in out)

    def test_fatigue_forgets_after_eight_events(self):
        s = SessionState("s")
        swipes(s, "cooking", 3)
        for i in range(8):
            push(s, "watch", 0.95, "music", i=10 + i)
        assert s.topic_fatigue().get("cooking", 0.0) == 0.0


# ----------------------------------------------------------------------------- no repeats

class TestNoRepeatsWithinSession:
    def test_consecutive_batches_are_disjoint(self):
        s = SessionState("s")
        vids = catalog()
        batches = [rank(profile(), s, vids, n=8, now=NOW, seed=k) for k in range(3)]
        ids = [{x.video.id for x in b} for b in batches]
        assert all(len(b) == 8 for b in batches)
        assert not (ids[0] & ids[1]) and not (ids[1] & ids[2]) and not (ids[0] & ids[2])

    def test_served_ids_are_recorded_on_the_session(self):
        s = SessionState("s")
        out = rank(profile(), s, catalog(), n=8, now=NOW, seed=0)
        assert {x.video.id for x in out} <= s.served

    def test_profile_seen_items_are_excluded(self):
        p = profile()
        p.seen = {0, 1, 2, 3, 4}
        out = rank(p, SessionState("s"), catalog(), n=20, now=NOW, seed=0)
        assert not ({x.video.id for x in out} & p.seen)

    def test_exhausted_pool_returns_fewer_items_never_repeats(self):
        s = SessionState("s")
        vids = [vid(i, "cooking") for i in range(10)]
        first = rank(profile(), s, vids, n=8, now=NOW, seed=0)
        second = rank(profile(), s, vids, n=8, now=NOW, seed=0)
        third = rank(profile(), s, vids, n=8, now=NOW, seed=0)
        assert len(first) == 8 and len(second) == 2 and third == []
        assert not ({x.video.id for x in first} & {x.video.id for x in second})

    def test_series_continuation_is_served_once(self):
        p = profile()
        p.series_progress = {7: 0}
        nxt = vid(500, "art", series_id=7, series_index=1)
        s = SessionState("s")
        first = rank(p, s, catalog() + [nxt], n=8, now=NOW, seed=0)
        assert first[0].video.id == nxt.id and first[0].slot == "series"
        second = rank(p, s, catalog() + [nxt], n=8, now=NOW, seed=0)
        assert nxt.id not in {x.video.id for x in second}


# ----------------------------------------------------------------------------- mood guard

class TestMoodGuard:
    def news(self, negatives: int, positives: int) -> list[Video]:
        neg = [vid(i, "news", sentiment=NEG) for i in range(negatives)]
        pos = [vid(100 + i, "news", sentiment=POS) for i in range(positives)]
        return neg + pos

    def test_never_three_negatives_in_a_row_within_a_batch(self):
        out = rank(profile(news=3.0), SessionState("s"), self.news(10, 10), n=8, now=NOW, seed=0)
        assert len(out) == 8
        assert max(negative_run_lengths(out)) <= MAX_NEGATIVE_RUN

    def test_negatives_just_watched_count_toward_the_run(self):
        s = SessionState("s")
        for i in range(MAX_NEGATIVE_RUN):
            push(s, "watch", 0.9, "news", sentiment=NEG, i=i)
        out = rank(profile(news=3.0), s, self.news(10, 10), n=8, now=NOW, seed=0)
        assert out[0].video.sentiment >= -0.3

    def test_all_negative_pool_returns_short_batch_not_a_doom_run(self):
        out = rank(profile(news=3.0), SessionState("s"), self.news(10, 0), n=8, now=NOW, seed=0)
        assert 0 < len(out) <= MAX_NEGATIVE_RUN

    def test_all_negative_pool_after_two_negatives_returns_nothing(self):
        s = SessionState("s")
        for i in range(MAX_NEGATIVE_RUN):
            push(s, "watch", 0.9, "news", sentiment=NEG, i=i)
        assert rank(profile(news=3.0), s, self.news(10, 0), n=8, now=NOW, seed=0) == []

    def test_positives_are_never_dropped_to_satisfy_the_guard(self):
        vids = self.news(10, 10)
        out = rank(profile(news=3.0), SessionState("s"), vids, n=20, now=NOW, seed=0)
        served = {x.video.id for x in out}
        assert {v.id for v in vids if v.sentiment >= -0.3} <= served
        assert max(negative_run_lengths(out)) <= MAX_NEGATIVE_RUN

    @pytest.mark.parametrize("seed", range(5))
    def test_guard_holds_across_a_whole_session(self, seed):
        """Simulate a 5-batch session where the client reports what it watched."""
        s, p, vids = SessionState("s"), profile(news=3.0), self.news(30, 30)
        served = []
        for _ in range(5):
            batch = rank(p, s, vids, n=8, now=NOW, seed=seed)
            for x in batch:
                push(s, "watch", 0.9, "news", sentiment=x.video.sentiment, i=x.video.id)
            served.extend(batch)
        assert served
        assert max(negative_run_lengths(served)) <= MAX_NEGATIVE_RUN


# ----------------------------------------------------------------------------- breakdown

class TestScoreBreakdown:
    def test_every_item_carries_every_signal(self):
        out = rank(profile(), SessionState("s"), catalog(), n=8, now=NOW, seed=0)
        assert len(out) == 8
        for s in out:
            assert set(SIGNALS) <= set(s.breakdown), s.breakdown
            assert all(math.isfinite(v) for v in s.breakdown.values())
            assert s.slot in {"exploit", "explore", "series"}

    def test_score_equals_sum_of_breakdown(self):
        p = profile()
        p.series_progress = {7: 0}
        vids = catalog() + [vid(500, "art", series_id=7, series_index=1)]
        for s in rank(p, SessionState("s"), vids, n=8, now=NOW, seed=0):
            assert math.isclose(s.score, sum(s.breakdown.values()))

    def test_series_item_explains_its_bonus(self):
        p = profile()
        p.series_progress = {7: 0}
        vids = catalog() + [vid(500, "art", series_id=7, series_index=1)]
        top = rank(p, SessionState("s"), vids, n=8, now=NOW, seed=0)[0]
        assert top.slot == "series" and top.breakdown["series"] == WEIGHTS["series"]

    def test_cohort_signal_is_attributed(self):
        out = rank(profile(), SessionState("s"), catalog(), n=20, now=NOW, seed=0,
                   cohort_scores={"art": 1.0})
        for s in out:
            expected = WEIGHTS["cohort"] if "art" in s.video.topics else 0.0
            assert s.breakdown["cohort"] == pytest.approx(expected)

    def test_cold_start_bonus_only_for_underexposed_videos(self):
        new = vid(700, "cooking", impressions=0, completions=0)
        old = vid(701, "cooking", impressions=1000, completions=600)
        out = {s.video.id: s for s in rank(profile(), SessionState("s"), [new, old], n=2, now=NOW, seed=0)}
        assert out[700].breakdown["cold_start"] == pytest.approx(WEIGHTS["cold_start"])
        assert out[701].breakdown["cold_start"] == 0.0

    def test_same_seed_is_reproducible(self):
        a = rank(profile(), SessionState("a"), catalog(), n=8, now=NOW, seed=42)
        b = rank(profile(), SessionState("b"), catalog(), n=8, now=NOW, seed=42)
        assert [(s.video.id, s.score, s.breakdown) for s in a] == [(s.video.id, s.score, s.breakdown) for s in b]

    def test_empty_candidates_returns_empty_list(self):
        assert rank(profile(), SessionState("s"), [], n=8, now=NOW, seed=0) == []
