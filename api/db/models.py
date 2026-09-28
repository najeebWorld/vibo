"""SQLAlchemy models mirroring engine/schema.sql (the source of truth; tests/test_schema_parity.py enforces it).

Types are chosen so the same models run on Postgres (production, created by Alembic from schema.sql)
and on SQLite (tests, created from this metadata).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

BigPK = BigInteger().with_variant(Integer, "sqlite")
Json = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    device_id: Mapped[str | None] = mapped_column(Text, unique=True)


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    creator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    hls_url: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    series_id: Mapped[int | None] = mapped_column(BigInteger)
    series_index: Mapped[int | None] = mapped_column(Integer)


class VideoTopic(Base):
    __tablename__ = "video_topics"
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    topic: Mapped[str] = mapped_column(Text, primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")


class Event(Base):
    """One row per client event. Never updated (CLAUDE.md: events are append-only)."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    watch_ms: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int | None] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VideoStats(Base):
    __tablename__ = "video_stats"
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avg_watch_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CohortTopicScore(Base):
    __tablename__ = "cohort_topic_scores"
    cohort_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)


class UserCohort(Base):
    __tablename__ = "user_cohort"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    cohort_id: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Trail(Base):
    """What a session left behind. kind: saved | series_progress | topic_unlocked | streak."""
    __tablename__ = "trails"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict | None] = mapped_column(Json)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MetricsDaily(Base):
    __tablename__ = "metrics_daily"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    dau: Mapped[int | None] = mapped_column(Integer)
    d1: Mapped[float | None] = mapped_column(Float)
    d7: Mapped[float | None] = mapped_column(Float)
    d30: Mapped[float | None] = mapped_column(Float)
    regret_proxy: Mapped[float | None] = mapped_column(Float)
    long_session_share: Mapped[float | None] = mapped_column(Float)
    median_ms_to_200: Mapped[int | None] = mapped_column(BigInteger)


class Report(Base):
    """UGC compliance: a user flagged a video. The video is hidden from that user immediately."""
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(BigPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("videos.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Block(Base):
    """UGC compliance: user_id never sees videos by blocked_user_id again."""
    __tablename__ = "blocks"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    blocked_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
