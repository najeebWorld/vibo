"""Creator feedback: where people leave a video. Computed live from events (not the 5-minute fold),
so a creator sees the curve minutes after upload.

  histogram[k]  views whose watch ratio landed in bucket k (k*10% .. (k+1)*10%), k = 0..9; >=100% is bucket 9
  retention[k]  share of views that reached at least k*10%, k = 0..10
  biggest_drop  the 10% segment where most viewers left: at_pct = start of that segment
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from api.db.models import Event, Video
from api.services.stats import VIEW_KINDS

BUCKETS = 10
COMPLETION = 0.9


@dataclass
class RetentionCurve:
    video_id: int
    duration_ms: int
    age_s: float
    views: int
    histogram: list[int] = field(default_factory=lambda: [0] * BUCKETS)
    retention: list[float] = field(default_factory=lambda: [0.0] * (BUCKETS + 1))
    completion_rate: float = 0.0
    avg_watch_ratio: float = 0.0
    biggest_drop: dict | None = None


def retention_curve(db: Session, video: Video, now: float | None = None) -> RetentionCurve:
    now = now or time.time()
    curve = RetentionCurve(video_id=video.id, duration_ms=video.duration_ms,
                           age_s=max(0.0, now - video.created_at.timestamp()), views=0)
    q = select(Event.watch_ms).where(Event.video_id == video.id, Event.kind.in_(VIEW_KINDS))
    ratios = [min(1.0, (ms or 0) / max(1, video.duration_ms)) for ms in db.scalars(q)]
    if not ratios:
        return curve
    curve.views = len(ratios)
    for r in ratios:
        curve.histogram[min(BUCKETS - 1, int(r * BUCKETS))] += 1
    curve.retention = [sum(1 for r in ratios if r >= k / BUCKETS) / len(ratios) for k in range(BUCKETS + 1)]
    curve.completion_rate = sum(1 for r in ratios if r >= COMPLETION) / len(ratios)
    curve.avg_watch_ratio = sum(ratios) / len(ratios)
    curve.biggest_drop = _biggest_drop(curve.retention)
    return curve


def _biggest_drop(retention: list[float]) -> dict | None:
    drops = [(retention[k - 1] - retention[k], k) for k in range(1, len(retention))]
    lost, k = max(drops, key=lambda d: d[0])
    return {"at_pct": (k - 1) * BUCKETS, "lost_share": lost} if lost > 0 else None


def my_videos(db: Session, user_id: int) -> list[dict]:
    """The creator's uploads, newest first, with live view counts."""
    is_view = Event.kind.in_(VIEW_KINDS)
    ratio = Event.watch_ms * 1.0 / Video.duration_ms
    stats = (
        select(
            Event.video_id,
            func.sum(case((is_view, 1), else_=0)).label("views"),
            func.sum(case((is_view & (ratio >= COMPLETION), 1), else_=0)).label("completions"),
            func.sum(case((is_view, case((ratio > 1.0, 1.0), else_=ratio)), else_=0.0)).label("ratio_sum"),
        )
        .join(Video, Video.id == Event.video_id)
        .where(Video.creator_id == user_id)
        .group_by(Event.video_id)
    )
    live = {row.video_id: row for row in db.execute(stats)}
    videos = db.scalars(select(Video).where(Video.creator_id == user_id)
                        .order_by(Video.created_at.desc(), Video.id.desc())).all()
    out = []
    for v in videos:
        s = live.get(v.id)
        views = int(s.views or 0) if s else 0
        out.append({
            "video_id": v.id, "creator_id": v.creator_id, "url": v.hls_url, "duration_ms": v.duration_ms,
            "created_at": v.created_at.timestamp(), "views": views,
            "completion_rate": (int(s.completions or 0) / views) if s and views else 0.0,
            "avg_watch_ratio": (float(s.ratio_sum or 0.0) / views) if s and views else 0.0,
        })
    return out
