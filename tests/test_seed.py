"""`make dev` seeds 200 synthetic videos + 30 synthetic users from engine/sim.py through the real ingest path."""
from __future__ import annotations

from sqlalchemy import func, select

from api.db.models import Event, Trail, User, Video, VideoStats
from api.seed import seed


def test_seed_creates_catalog_users_and_warm_profiles(app, db):
    result = seed(db, app.state.profiles, app.state.sessions, n_videos=200, n_users=30, sample_url="http://x/v.mp4")
    assert result == {"videos": 200, "users": 30, "events": result["events"], "skipped": False}

    assert db.scalar(select(func.count()).select_from(Video)) == 200
    assert db.scalar(select(func.count()).select_from(User)) == 30
    assert db.scalar(select(func.count()).select_from(Event)) == result["events"] > 0
    assert db.scalar(select(func.count()).select_from(VideoStats).where(VideoStats.impressions > 0)) > 100
    assert all(v.hls_url for v in db.scalars(select(Video)))

    first = db.scalar(select(User).where(User.device_id == "sim-0"))
    assert app.state.profiles.load(first.id).topics, "seeded users have a warm taste profile"


def test_seed_leaves_trails_for_sessions_with_completions(app, db):
    seed(db, app.state.profiles, app.state.sessions, n_videos=60, n_users=5, sample_url="http://x/v.mp4")
    streak_sessions = {t.session_id for t in db.scalars(select(Trail).where(Trail.kind == "streak"))}
    completed = db.execute(
        select(Event.session_id).join(Video, Video.id == Event.video_id)
        .where(Event.kind.in_(["watch", "rewatch", "save", "share"]), Event.watch_ms >= 0.9 * Video.duration_ms)
    ).scalars().all()
    assert set(completed) and set(completed) <= streak_sessions


def test_seed_is_idempotent(app, db):
    seed(db, app.state.profiles, app.state.sessions, n_videos=20, n_users=3, sample_url="http://x/v.mp4")
    again = seed(db, app.state.profiles, app.state.sessions, n_videos=20, n_users=3, sample_url="http://x/v.mp4")
    assert again["skipped"] is True
    assert db.scalar(select(func.count()).select_from(Video)) == 20
