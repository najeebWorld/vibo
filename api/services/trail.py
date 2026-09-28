"""The trail: what a session leaves behind (anti-emptiness, weakness #1).

Rules
  save                      -> 'saved'
  series item watched >=70% -> 'series_progress' (+ profile series pointer, which drives the ranker's series slot)
  first completion in topic -> 'topic_unlocked'
  any completion            -> the session's single 'streak' row is created/bumped

The streak row is what guarantees CLAUDE.md's invariant: a session with >=1 completion always has a trail.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import Trail
from api.services.catalog import main_topic
from api.stores import ProfileStore
from engine.models import Video

COMPLETION = 0.9
SERIES_PROGRESS = 0.7


def leave_trail(db: Session, profiles: ProfileStore, user_id: int, session_id: uuid.UUID,
                video: Video, kind: str, ratio: float) -> list[Trail]:
    added: list[Trail] = []
    if kind == "save":
        added.append(_add(db, user_id, session_id, "saved", video.id, {"topics": video.topics}))
    if video.series_id is not None and ratio >= SERIES_PROGRESS:
        profiles.set_series_progress(user_id, video.series_id, video.series_index or 0)
        added.append(_add(db, user_id, session_id, "series_progress", video.series_id,
                          {"index": video.series_index, "video_id": video.id}))
    if ratio >= COMPLETION or kind in ("save", "share"):
        topic = main_topic(video)
        if topic and profiles.unlock_topic(user_id, topic):
            added.append(_add(db, user_id, session_id, "topic_unlocked", None, {"topic": topic}))
        added.append(_bump_streak(db, user_id, session_id, video.id))
    return added


def _add(db: Session, user_id: int, session_id: uuid.UUID, kind: str, ref_id: int | None, payload: dict) -> Trail:
    t = Trail(user_id=user_id, session_id=session_id, kind=kind, ref_id=ref_id, payload=payload)
    db.add(t)
    db.flush()
    return t


def _bump_streak(db: Session, user_id: int, session_id: uuid.UUID, video_id: int) -> Trail:
    row = db.scalar(select(Trail).where(Trail.session_id == session_id, Trail.kind == "streak"))
    if row is None:
        return _add(db, user_id, session_id, "streak", None, {"completions": 1, "video_ids": [video_id]})
    p = dict(row.payload or {})
    ids = list(p.get("video_ids", []))
    if video_id in ids:            # watch + save of the same video is one completion, not two
        return row
    ids.append(video_id)
    row.payload = {"completions": len(ids), "video_ids": ids}
    db.flush()
    return row
