from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from api.db.models import Block, Report, Trail, User, Video, VideoStats, VideoTopic
from api.deps import Ctx, get_ctx, get_db
from api.schemas import (BlockIn, EventsBatch, FeedItem, FeedOut, IngestOut, MyVideosOut, ReportIn, RetentionOut,
                         TrailItem, TrailOut, UserIn, UserOut, VideoIn, VideoOut)
from api.services.feed import build_feed
from api.services.ingest import UnknownVideo, ingest_batch
from api.services.retention import my_videos, retention_curve
from api.services.users import resolve_user
from api.storage import LocalStorage

router = APIRouter()


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    db_ok = redis_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    try:
        redis_ok = bool(request.app.state.redis.ping())
    except Exception:
        pass
    return {"ok": db_ok and redis_ok, "db": db_ok, "redis": redis_ok}


@router.post("/users", response_model=UserOut)
def register_user(body: UserIn, db: Session = Depends(get_db)):
    uid = resolve_user(db, body.device_id)
    db.commit()
    return UserOut(user_id=uid)


@router.post("/events", response_model=IngestOut)
def post_events(body: EventsBatch, db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    uid = resolve_user(db, body.user_id)
    try:
        result = ingest_batch(db, ctx.profiles, ctx.sessions, uid, body.session_id, body.events, now=time.time())
    except UnknownVideo as e:
        raise HTTPException(404, f"unknown video ids: {e.args[0]}")
    return IngestOut(accepted=result.accepted, user_id=uid, trail=[_trail_item(t) for t in result.trail])


@router.get("/feed", response_model=FeedOut)
def get_feed(user_id: str, session_id: UUID, n: int = Query(8, ge=1, le=20),
             db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    uid = resolve_user(db, user_id)
    db.commit()
    ranked = build_feed(db, ctx.profiles, ctx.sessions, uid, str(session_id), n=n, now=time.time(),
                        candidates=ctx.settings.candidates)
    items = [
        FeedItem(video_id=s.video.id, creator_id=it.creator_id, url=it.url, duration_ms=s.video.duration_ms, topics=s.video.topics,
                 sentiment=s.video.sentiment, series_id=s.video.series_id, series_index=s.video.series_index,
                 score=s.score, slot=s.slot, breakdown=s.breakdown)
        for s, it in ranked
    ]
    return FeedOut(user_id=uid, session_id=session_id, items=items)


@router.post("/videos", response_model=VideoOut)
def create_video(body: VideoIn, db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    creator = resolve_user(db, body.creator_id) if body.creator_id else None
    v = Video(creator_id=creator, duration_ms=body.duration_ms, sentiment=body.sentiment,
              series_id=body.series_id, series_index=body.series_index)
    db.add(v)
    db.flush()
    total = sum(body.topics.values()) or 1.0
    db.add_all([VideoTopic(video_id=v.id, topic=t, weight=w / total) for t, w in body.topics.items()])
    db.add(VideoStats(video_id=v.id))
    db.commit()
    return VideoOut(video_id=v.id, upload_url=ctx.storage.presigned_upload(_key(v.id), body.content_type), url=None)


@router.post("/videos/{video_id}/complete")
def complete_upload(video_id: int, db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    """Marks the video playable. Local storage calls this itself after the PUT; S3 clients call it after upload.
    Transcoding to HLS is phase 2: for now the source file is what gets played."""
    v = db.get(Video, video_id)
    if v is None:
        raise HTTPException(404, "unknown video")
    v.hls_url = ctx.storage.public_url(_key(video_id))
    db.commit()
    return {"video_id": video_id, "url": v.hls_url}


@router.put("/uploads/{key:path}")
async def local_upload(key: str, token: str, expires: int, request: Request,
                       db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    storage = ctx.storage
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404, "local uploads are disabled")
    if not storage.verify(key, token, expires):
        raise HTTPException(403, "bad or expired upload token")
    storage.put(key, await request.body())
    return complete_upload(_video_id_from_key(key), db, ctx)


@router.post("/videos/{video_id}/report")
def report_video(video_id: int, body: ReportIn, db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    """UGC compliance: record the report and hide the video from this user immediately."""
    if db.get(Video, video_id) is None:
        raise HTTPException(404, "unknown video")
    uid = resolve_user(db, body.user_id)
    db.add(Report(user_id=uid, video_id=video_id, reason=body.reason))
    db.commit()
    ctx.profiles.hide(uid, video_id)
    return {"video_id": video_id, "hidden": True}


@router.post("/users/block")
def block_user(body: BlockIn, db: Session = Depends(get_db)):
    """UGC compliance: the blocker never sees the blocked creator's videos again. Idempotent."""
    if db.get(User, body.blocked_user_id) is None:
        raise HTTPException(404, "unknown user")
    uid = resolve_user(db, body.user_id)
    db.merge(Block(user_id=uid, blocked_user_id=body.blocked_user_id))
    db.commit()
    return {"user_id": uid, "blocked_user_id": body.blocked_user_id, "ok": True}


@router.get("/videos/{video_id}/retention", response_model=RetentionOut)
def video_retention(video_id: int, db: Session = Depends(get_db)):
    """Creator feedback: watch-ratio histogram (10% buckets) and retention curve, live from events."""
    v = db.get(Video, video_id)
    if v is None:
        raise HTTPException(404, "unknown video")
    return RetentionOut(**retention_curve(db, v).__dict__)


@router.get("/me/videos", response_model=MyVideosOut)
def list_my_videos(user_id: str, db: Session = Depends(get_db)):
    uid = resolve_user(db, user_id)
    db.commit()
    return MyVideosOut(user_id=uid, items=my_videos(db, uid))


@router.get("/me/trail", response_model=TrailOut)
def my_trail(user_id: str, session_id: UUID | None = None, since: float | None = None,
             limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    uid = resolve_user(db, user_id)
    db.commit()
    q = select(Trail).where(Trail.user_id == uid)
    if session_id is not None:
        q = q.where(Trail.session_id == session_id)
    if since is not None:
        from datetime import datetime, timezone
        q = q.where(Trail.ts >= datetime.fromtimestamp(since, tz=timezone.utc))
    rows = db.scalars(q.order_by(Trail.ts.desc(), Trail.id.desc()).limit(limit)).all()
    return TrailOut(user_id=uid, items=[_trail_item(t) for t in rows])


def _key(video_id: int) -> str:
    return f"videos/{video_id}/source.mp4"


def _video_id_from_key(key: str) -> int:
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "videos" or not parts[1].isdigit():
        raise HTTPException(400, "malformed upload key")
    return int(parts[1])


def _trail_item(t: Trail) -> TrailItem:
    return TrailItem(id=t.id, kind=t.kind, ref_id=t.ref_id, payload=t.payload, session_id=t.session_id,
                     ts=t.ts.timestamp() if t.ts else time.time())
