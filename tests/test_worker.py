"""worker/: 5-minute stats fold, hourly cohorts (k-means k=8), daily retention + guardrail metrics."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from api.db.models import CohortTopicScore, Event, MetricsDaily, UserCohort, Video, VideoStats
from api.services.users import resolve_user
from engine.cohort import kmeans, topic_lift
from engine.models import Event as TasteEvent
from tests.conftest import create_video, new_session_id, post_events, watch
from worker.cohorts import compute_cohorts
from worker.cron import SCHEDULE
from worker.metrics import compute_daily_metrics, format_summary
from worker.stats import fold_stats

DAY = date(2026, 9, 20)


def ts(day: date, minutes: float = 0.0) -> float:
    return (datetime(day.year, day.month, day.day, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)).timestamp()


# ----------------------------------------------------------------------------- engine/cohort.py (pure)

class TestKMeans:
    def test_separates_two_obvious_groups(self):
        cooks = [{"cooking": 1.0, "music": 0.1}] * 3
        music = [{"music": 1.0, "cooking": 0.1}] * 3
        labels = kmeans(cooks + music, k=2, seed=0)
        assert len(set(labels[:3])) == 1 and len(set(labels[3:])) == 1 and labels[0] != labels[3]

    def test_k_larger_than_population_is_clamped(self):
        labels = kmeans([{"a": 1.0}, {"b": 1.0}], k=8, seed=0)
        assert len(labels) == 2 and max(labels) < 2

    def test_empty_input(self):
        assert kmeans([], k=8, seed=0) == []

    def test_deterministic_for_seed(self):
        vecs = [{"a": float(i % 3), "b": float(i % 5)} for i in range(20)]
        assert kmeans(vecs, k=4, seed=1) == kmeans(vecs, k=4, seed=1)

    def test_topic_lift_marks_over_indexed_topics(self):
        vecs = [{"cooking": 1.0}, {"cooking": 0.8, "art": 0.2}, {"music": 1.0}, {"music": 0.9, "art": 0.1}]
        lift = topic_lift(vecs, [0, 0, 1, 1])
        assert lift[0]["cooking"] == pytest.approx(1.0) and "music" not in lift[0]
        assert lift[1]["music"] == pytest.approx(1.0) and "cooking" not in lift[1]
        assert all(0.0 <= v <= 1.0 for c in lift.values() for v in c.values())


# ----------------------------------------------------------------------------- cohorts job

def warm_profile(app, db, device: str, topic: str) -> int:
    uid = resolve_user(db, device)
    db.commit()
    for i in range(3):
        app.state.profiles.apply(uid, TasteEvent(1000 + i, "watch", 1.0, {topic: 1.0}, ts(DAY)), now=ts(DAY))
    return uid


def test_cohorts_group_users_by_taste_and_score_topics(app, db, client):
    cooks = [warm_profile(app, db, f"cook-{i}", "cooking") for i in range(3)]
    musos = [warm_profile(app, db, f"muso-{i}", "music") for i in range(3)]
    resolve_user(db, "never-watched")
    db.commit()

    result = compute_cohorts(db, app.state.profiles, k=2, now=ts(DAY))
    assert result["users"] == 6 and result["cohorts"] == 2

    cohort_of = {uc.user_id: uc.cohort_id for uc in db.scalars(select(UserCohort))}
    assert len(cohort_of) == 6, "users without a profile are not assigned"
    assert len({cohort_of[u] for u in cooks}) == 1 and len({cohort_of[u] for u in musos}) == 1
    assert cohort_of[cooks[0]] != cohort_of[musos[0]]

    scores = {(s.cohort_id, s.topic): s.score for s in db.scalars(select(CohortTopicScore))}
    assert scores[(cohort_of[cooks[0]], "cooking")] == pytest.approx(1.0)
    assert (cohort_of[cooks[0]], "music") not in scores


def test_cohort_scores_reach_the_feed_breakdown(app, db, client):
    for t in ("cooking", "music"):
        for _ in range(6):
            create_video(client, t)
    cooks = [warm_profile(app, db, f"cook-{i}", "cooking") for i in range(3)]
    [warm_profile(app, db, f"muso-{i}", "music") for i in range(3)]
    compute_cohorts(db, app.state.profiles, k=2, now=ts(DAY))

    items = client.get("/feed", params={"user_id": cooks[0], "session_id": new_session_id(), "n": 8}).json()["items"]
    cooking = [i for i in items if "cooking" in i["topics"]]
    assert cooking and all(i["breakdown"]["cohort"] > 0 for i in cooking)
    assert all(i["breakdown"]["cohort"] == 0 for i in items if "music" in i["topics"])


def test_cohorts_rerun_replaces_previous_assignment(app, db, client):
    [warm_profile(app, db, f"u-{i}", "cooking") for i in range(4)]
    compute_cohorts(db, app.state.profiles, k=2, now=ts(DAY))
    compute_cohorts(db, app.state.profiles, k=2, now=ts(DAY))
    assert db.scalar(select(func.count()).select_from(UserCohort)) == 4


# ----------------------------------------------------------------------------- stats fold job

def test_fold_stats_aggregates_views_completions_and_saves(client, db):
    v = create_video(client, "cooking")
    other = create_video(client, "art")
    sid = new_session_id()
    post_events(client, "u1", sid, [watch(v, 1.0), watch(v, 0.2, kind="swipe"), watch(v, 1.0, kind="save"), watch(other, 0.5)])
    post_events(client, "u2", new_session_id(), [{"video_id": v["video_id"], "kind": "impression"}])

    assert fold_stats(db) == 2
    s = db.get(VideoStats, v["video_id"])
    assert (s.impressions, s.completions, s.saves, s.shares) == (2, 1, 1, 0)
    assert s.avg_watch_ratio == pytest.approx(0.6)


# ----------------------------------------------------------------------------- daily metrics job

def session(client, user: str, day: date, start_min: float, length_min: float, last_ratio: float, video: dict) -> None:
    sid = new_session_id()
    first = {**watch(video, 1.0, position=0), "ts": ts(day, start_min)}
    kind = "swipe" if last_ratio < 0.5 else "watch"
    last = {**watch(video, last_ratio, kind=kind, position=1), "ts": ts(day, start_min + length_min)}
    post_events(client, user, sid, [first, last])


def seed_activity(client) -> dict:
    v = create_video(client, "cooking")
    # D-1 cohort: u1,u2,u3 -> u1,u2 return on D            => d1 = 2/3
    for u in ("u1", "u2", "u3"):
        session(client, u, DAY - timedelta(days=1), 0, 3, 1.0, v)
    # D-7 cohort: u4,u5 -> u4 returns                       => d7 = 1/2
    for u in ("u4", "u5"):
        session(client, u, DAY - timedelta(days=7), 0, 3, 1.0, v)
    # D-30 cohort: u6 -> returns                            => d30 = 1/1
    session(client, "u6", DAY - timedelta(days=30), 0, 3, 1.0, v)
    # sessions on D
    session(client, "u1", DAY, 0, 25, 0.1, v)     # >20 min, abrupt close (left mid-video)  -> regret
    session(client, "u2", DAY, 0, 50, 1.0, v)     # >45 min, clean end                       -> long
    session(client, "u4", DAY, 0, 5, 1.0, v)      # short
    session(client, "u6", DAY, 0, 22, 0.95, v)    # >20 min, clean end
    return v


def test_daily_metrics_retention_and_guardrails(client, db, capsys):
    seed_activity(client)
    row = compute_daily_metrics(db, DAY)
    assert row.dau == 4
    assert row.d1 == pytest.approx(2 / 3) and row.d7 == pytest.approx(0.5) and row.d30 == pytest.approx(1.0)
    assert row.regret_proxy == pytest.approx(1 / 3)
    assert row.long_session_share == pytest.approx(1 / 4)
    assert row.median_ms_to_200 is None
    print(format_summary(row))
    out = capsys.readouterr().out
    assert "d7" in out and "regret" in out


def test_daily_metrics_upserts_one_row_per_day(client, db):
    seed_activity(client)
    compute_daily_metrics(db, DAY)
    compute_daily_metrics(db, DAY)
    assert db.scalar(select(func.count()).select_from(MetricsDaily)) == 1
    assert db.get(MetricsDaily, DAY).dau == 4


def test_daily_metrics_on_an_empty_day(client, db):
    row = compute_daily_metrics(db, DAY)
    assert row.dau == 0 and row.d1 is None and row.regret_proxy is None and row.long_session_share is None


def test_median_ms_to_200_impressions(client, db):
    v = create_video(client, "cooking")
    uid = resolve_user(db, "bulk")
    created = db.get(Video, v["video_id"]).created_at
    sid = uuid.uuid4()
    for i in range(200):
        db.add(Event(user_id=uid, session_id=sid, video_id=v["video_id"], kind="watch", watch_ms=5000,
                     ts=created + timedelta(minutes=i + 1)))
    db.commit()
    row = compute_daily_metrics(db, created.date())
    assert row.median_ms_to_200 == 200 * 60 * 1000


# ----------------------------------------------------------------------------- schedule

def test_schedule_matches_the_spec():
    by_name = {s["name"]: s for s in SCHEDULE}
    assert by_name["fold_stats"]["interval"] == 5 * 60
    assert by_name["compute_cohorts"]["interval"] == 60 * 60
    minute, hour, *rest = by_name["daily_metrics"]["cron"].split()
    assert minute.isdigit() and hour.isdigit() and rest == ["*", "*", "*"], "once a day at a fixed time"
