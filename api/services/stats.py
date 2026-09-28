"""Fold append-only events into video_stats. Called by the worker every 5 minutes and by the seed."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from api.db.models import Event, Video, VideoStats

VIEW_KINDS = ("watch", "swipe", "rewatch")


def fold_events_into_stats(db: Session) -> int:
    """Full recompute (phase 1 volumes are tiny). Returns number of videos updated."""
    raw_ratio = Event.watch_ms * 1.0 / Video.duration_ms
    ratio = case((raw_ratio > 1.0, 1.0), else_=raw_ratio)   # portable min(1, x): PG has no 2-arg min
    is_view = Event.kind.in_(VIEW_KINDS)
    q = (
        select(
            Event.video_id,
            func.sum(case((is_view, 1), else_=0)).label("impressions"),
            func.sum(case((is_view & (Event.watch_ms >= 0.9 * Video.duration_ms), 1), else_=0)).label("completions"),
            func.sum(case((is_view, ratio), else_=0.0)).label("ratio_sum"),
            func.sum(case((Event.kind == "share", 1), else_=0)).label("shares"),
            func.sum(case((Event.kind == "save", 1), else_=0)).label("saves"),
        )
        .join(Video, Video.id == Event.video_id)
        .group_by(Event.video_id)
    )
    existing = {s.video_id: s for s in db.scalars(select(VideoStats))}
    n = 0
    for row in db.execute(q):
        s = existing.get(row.video_id) or VideoStats(video_id=row.video_id)
        s.impressions = int(row.impressions or 0)
        s.completions = int(row.completions or 0)
        s.avg_watch_ratio = float(row.ratio_sum or 0.0) / s.impressions if s.impressions else 0.0
        s.shares = int(row.shares or 0)
        s.saves = int(row.saves or 0)
        s.updated_at = func.now()
        db.add(s)
        n += 1
    db.commit()
    return n
