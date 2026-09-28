"""POST /events: append rows, fold into the Redis profile + session, leave the trail."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db.models import Event as EventRow
from api.db.models import Trail
from api.schemas import EventIn
from api.services.catalog import load_items
from api.services.trail import leave_trail
from api.stores import ProfileStore, SessionStore
from engine.models import Event, Video

TASTE_KINDS = {"watch", "swipe", "rewatch", "share", "save"}   # impression/pause are logged but don't move taste
MAX_RATIO = 1.3


class UnknownVideo(LookupError):
    pass


@dataclass
class IngestResult:
    accepted: int
    trail: list[Trail]


def ingest_batch(db: Session, profiles: ProfileStore, sessions: SessionStore, user_id: int,
                 session_id: uuid.UUID, events: list[EventIn], now: float) -> IngestResult:
    items = load_items(db, ids=sorted({e.video_id for e in events}), playable_only=False)
    missing = {e.video_id for e in events} - set(items)
    if missing:
        raise UnknownVideo(sorted(missing))

    trail: list[Trail] = []
    for e in events:
        ts = e.ts if e.ts is not None else now
        db.add(EventRow(user_id=user_id, session_id=session_id, video_id=e.video_id, kind=e.kind,
                        watch_ms=e.watch_ms, position=e.position, ts=datetime.fromtimestamp(ts, tz=timezone.utc)))
        if e.kind not in TASTE_KINDS:
            continue
        video = items[e.video_id].video
        ratio = watch_ratio(e, video)
        profiles.apply(user_id, Event(video.id, e.kind, ratio, video.topics, ts), now)
        sessions.push(str(session_id), Event(video.id, e.kind, ratio, {**video.topics, "__sentiment__": video.sentiment}, ts))
        trail.extend(leave_trail(db, profiles, user_id, session_id, video, e.kind, ratio))
    db.commit()
    return IngestResult(accepted=len(events), trail=_dedupe(trail))


def watch_ratio(e: EventIn, video: Video) -> float:
    if e.watch_ms is None:
        return 1.0 if e.kind in ("share", "save", "rewatch") else 0.0
    return min(MAX_RATIO, e.watch_ms / max(1, video.duration_ms))


def _dedupe(rows: list[Trail]) -> list[Trail]:
    """The streak row is bumped per completion; report it once with its final payload."""
    out: dict[int, Trail] = {}
    for t in rows:
        out[t.id] = t
    return list(out.values())
