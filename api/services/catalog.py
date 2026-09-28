"""Map video rows to engine.models.Video and back."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.models import Video as VideoRow
from api.db.models import VideoStats, VideoTopic
from engine.models import Video


@dataclass
class CatalogItem:
    video: Video
    url: str
    creator_id: int | None


def load_items(db: Session, ids: list[int] | None = None, *, playable_only: bool = True,
               exclude: set[int] = frozenset(), exclude_creators: set[int] = frozenset(),
               limit: int | None = None) -> dict[int, CatalogItem]:
    """Fetch videos (+topics +stats) as engine objects. With `limit`, a random sample of the pool."""
    q = select(VideoRow, VideoStats).outerjoin(VideoStats, VideoStats.video_id == VideoRow.id)
    if ids is not None:
        q = q.where(VideoRow.id.in_(ids))
    if playable_only:
        q = q.where(VideoRow.hls_url.is_not(None))
    if exclude:
        q = q.where(VideoRow.id.not_in(exclude))
    if exclude_creators:
        q = q.where(VideoRow.creator_id.is_(None) | VideoRow.creator_id.not_in(exclude_creators))
    if limit:
        q = q.order_by(func.random()).limit(limit)
    rows = db.execute(q).all()
    topics = _topics_for(db, [r.id for r, _ in rows])
    return {r.id: _to_item(r, s, topics.get(r.id, {})) for r, s in rows}


def _topics_for(db: Session, ids: list[int]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    if not ids:
        return out
    for t in db.scalars(select(VideoTopic).where(VideoTopic.video_id.in_(ids))):
        out.setdefault(t.video_id, {})[t.topic] = t.weight
    return out


def _to_item(r: VideoRow, s: VideoStats | None, topics: dict[str, float]) -> CatalogItem:
    v = Video(
        id=r.id,
        topics=topics,
        duration_ms=r.duration_ms,
        created_ts=r.created_at.timestamp(),
        sentiment=r.sentiment,
        series_id=r.series_id,
        series_index=r.series_index,
        impressions=s.impressions if s else 0,
        completions=s.completions if s else 0,
        watch_ratio_sum=(s.avg_watch_ratio * s.impressions) if s else 0.0,
    )
    return CatalogItem(video=v, url=r.hls_url or "", creator_id=r.creator_id)


def main_topic(v: Video) -> str:
    return max(v.topics, key=v.topics.get) if v.topics else ""
