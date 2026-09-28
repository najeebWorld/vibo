"""Request/response models."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EventKind = Literal["impression", "watch", "swipe", "rewatch", "share", "save", "pause"]


class UserIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    user_id: int


class EventIn(BaseModel):
    video_id: int
    kind: EventKind
    watch_ms: int | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=0)
    ts: float | None = None            # epoch seconds from the device; server time if omitted


class EventsBatch(BaseModel):
    user_id: str                       # numeric id or device id
    session_id: UUID
    events: list[EventIn] = Field(max_length=500)


class TrailItem(BaseModel):
    id: int
    kind: str
    ref_id: int | None
    payload: dict[str, Any] | None
    session_id: UUID
    ts: float


class IngestOut(BaseModel):
    accepted: int
    user_id: int
    trail: list[TrailItem]


class FeedItem(BaseModel):
    video_id: int
    creator_id: int | None
    url: str
    duration_ms: int
    topics: dict[str, float]
    sentiment: float
    series_id: int | None
    series_index: int | None
    score: float
    slot: str
    breakdown: dict[str, float]


class FeedOut(BaseModel):
    user_id: int
    session_id: UUID
    items: list[FeedItem]


class VideoIn(BaseModel):
    creator_id: str | None = None
    duration_ms: int = Field(gt=0)
    topics: dict[str, float] = Field(min_length=1)
    sentiment: float = Field(default=0.0, ge=-1, le=1)
    series_id: int | None = None
    series_index: int | None = None
    content_type: str = "video/mp4"


class VideoOut(BaseModel):
    video_id: int
    upload_url: str
    url: str | None


ReportReason = Literal["spam", "harassment", "violence", "sexual", "misinformation", "other"]


class ReportIn(BaseModel):
    user_id: str
    reason: ReportReason


class BlockIn(BaseModel):
    user_id: str
    blocked_user_id: int


class RetentionOut(BaseModel):
    video_id: int
    duration_ms: int
    age_s: float
    views: int
    histogram: list[int]          # 10 buckets of 10% watch ratio
    retention: list[float]        # 11 points: share of views reaching >= k*10%
    completion_rate: float
    avg_watch_ratio: float
    biggest_drop: dict[str, float] | None


class MyVideoItem(BaseModel):
    video_id: int
    creator_id: int | None
    url: str | None
    duration_ms: int
    created_at: float
    views: int
    completion_rate: float
    avg_watch_ratio: float


class MyVideosOut(BaseModel):
    user_id: int
    items: list[MyVideoItem]


class TrailOut(BaseModel):
    user_id: int
    items: list[TrailItem]
