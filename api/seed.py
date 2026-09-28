"""Seed 200 synthetic videos + 30 synthetic users from engine/sim.py, through the real ingest path.

Run inside the api container: python -m api.seed
Each user "watches" a first session so profiles are warm, video_stats are non-zero and trails exist.
"""
from __future__ import annotations

import random
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import User, Video, VideoStats, VideoTopic
from api.schemas import EventIn
from api.services.ingest import ingest_batch
from api.services.stats import fold_events_into_stats
from api.stores import ProfileStore, SessionStore
from engine import sim

SESSION_LEN = 24


def seed(db: Session, profiles: ProfileStore, sessions: SessionStore, n_videos: int = 200, n_users: int = 30,
         sample_url: str = "", rng_seed: int = 7, now: float | None = None) -> dict:
    if db.scalar(select(User).where(User.device_id == "sim-0")) is not None:
        return {"videos": 0, "users": 0, "events": 0, "skipped": True}
    now = now or time.time()
    rng = random.Random(rng_seed)
    sim_users = sim.make_users(n_users, rng)
    sim_videos = sim.make_videos(n_videos, rng, now)

    user_ids = _insert_users(db, n_users)
    video_ids = _insert_videos(db, sim_videos, user_ids, sample_url, rng)
    db.commit()

    videos_by_id = {video_ids[v.id]: v for v in sim_videos}
    events = 0
    for i, u in enumerate(sim_users):
        batch = _first_session(u, videos_by_id, rng)
        ingest_batch(db, profiles, sessions, user_ids[i], uuid.uuid4(), batch, now)
        events += len(batch)
    fold_events_into_stats(db)
    return {"videos": n_videos, "users": n_users, "events": events, "skipped": False}


def _insert_users(db: Session, n: int) -> list[int]:
    rows = [User(device_id=f"sim-{i}") for i in range(n)]
    db.add_all(rows)
    db.flush()
    return [r.id for r in rows]


def _insert_videos(db: Session, vids: list[sim.Video], user_ids: list[int], sample_url: str, rng: random.Random) -> dict[int, int]:
    from datetime import datetime, timezone

    mapping: dict[int, int] = {}
    for v in vids:
        row = Video(creator_id=rng.choice(user_ids), duration_ms=v.duration_ms, hls_url=sample_url or None,
                    sentiment=v.sentiment, series_id=v.series_id, series_index=v.series_index,
                    created_at=datetime.fromtimestamp(v.created_ts, tz=timezone.utc))
        db.add(row)
        db.flush()
        db.add_all([VideoTopic(video_id=row.id, topic=t, weight=w) for t, w in v.topics.items()])
        db.add(VideoStats(video_id=row.id))
        mapping[v.id] = row.id
    return mapping


def _first_session(u: sim.SimUser, videos: dict[int, sim.Video], rng: random.Random) -> list[EventIn]:
    """Random sample, watched according to the user's hidden taste (sim.watch_ratio)."""
    batch: list[EventIn] = []
    for pos, vid in enumerate(rng.sample(sorted(videos), min(SESSION_LEN, len(videos)))):
        v = videos[vid]
        r = sim.watch_ratio(u, v, rng, fatigue=0.0)
        kind = "swipe" if r < 0.5 else ("rewatch" if r > 1.0 else "watch")
        if r > 0.9 and rng.random() < 0.15:
            kind = "save"
        batch.append(EventIn(video_id=vid, kind=kind, watch_ms=int(r * v.duration_ms), position=pos))
    return batch


def main() -> None:
    import redis

    from api.config import Settings
    from api.db.session import make_engine, make_sessionmaker

    settings = Settings.from_env()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    with make_sessionmaker(make_engine(settings.database_url))() as db:
        result = seed(db, ProfileStore(r), SessionStore(r), sample_url=settings.seed_sample_url)
    print("seed:", result)


if __name__ == "__main__":
    main()
