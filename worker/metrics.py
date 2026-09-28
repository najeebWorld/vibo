"""Daily: retention + guardrails -> metrics_daily. Definitions (also in docs/CHANGELOG.md):

  dau                 distinct users with a taste event on `day` (UTC)
  d1 / d7 / d30       of the users active on day-k, the share also active on `day`  (activity-based return rate)
  regret_proxy        of sessions on `day` longer than 20 min, the share that ended mid-video
                      (last event is a swipe, or a watch with ratio < 0.5)                         GUARDRAIL
  long_session_share  share of sessions on `day` longer than 45 min                                GUARDRAIL
  median_ms_to_200    of videos uploaded on `day` that reached 200 views, median ms from upload to the 200th
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import Event, MetricsDaily, Video
from api.services.ingest import TASTE_KINDS
from api.services.stats import VIEW_KINDS

REGRET_MIN_S = 20 * 60
LONG_MIN_S = 45 * 60
ABRUPT_RATIO = 0.5
REACH = 200


@dataclass
class SessionSummary:
    user_id: int
    start: datetime
    end: datetime
    last_kind: str
    last_ratio: float

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    @property
    def abrupt(self) -> bool:
        return self.last_kind == "swipe" or (self.last_kind == "watch" and self.last_ratio < ABRUPT_RATIO)


def compute_daily_metrics(db: Session, day: date) -> MetricsDaily:
    sessions = load_sessions(db, day)
    active = active_users(db, day)
    long_ = [s for s in sessions if s.seconds > REGRET_MIN_S]
    row = db.get(MetricsDaily, day) or MetricsDaily(day=day)
    row.dau = len(active)
    row.d1, row.d7, row.d30 = (retention(db, day, k, active) for k in (1, 7, 30))
    row.regret_proxy = _share([s for s in long_ if s.abrupt], long_)
    row.long_session_share = _share([s for s in sessions if s.seconds > LONG_MIN_S], sessions)
    row.median_ms_to_200 = median_ms_to_reach(db, day)
    db.add(row)
    db.commit()
    return row


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def active_users(db: Session, day: date) -> set[int]:
    start, end = day_bounds(day)
    q = select(Event.user_id).where(Event.ts >= start, Event.ts < end, Event.kind.in_(TASTE_KINDS)).distinct()
    return set(db.scalars(q))


def retention(db: Session, day: date, k: int, active_today: set[int]) -> float | None:
    base = active_users(db, day - timedelta(days=k))
    return len(base & active_today) / len(base) if base else None


def load_sessions(db: Session, day: date) -> list[SessionSummary]:
    """Sessions are derived from events (no session table): grouped by session_id, taste events only."""
    start, end = day_bounds(day)
    q = (select(Event.session_id, Event.user_id, Event.ts, Event.kind, Event.watch_ms, Video.duration_ms)
         .join(Video, Video.id == Event.video_id)
         .where(Event.ts >= start, Event.ts < end, Event.kind.in_(TASTE_KINDS))
         .order_by(Event.session_id, Event.ts, Event.id))
    out: dict = {}
    for sid, uid, ts, kind, watch_ms, duration in db.execute(q):
        ratio = (watch_ms or 0) / max(1, duration)
        s = out.get(sid)
        if s is None:
            out[sid] = SessionSummary(uid, ts, ts, kind, ratio)
        else:
            s.end, s.last_kind, s.last_ratio = ts, kind, ratio
    return list(out.values())


def median_ms_to_reach(db: Session, day: date, reach: int = REACH) -> int | None:
    start, end = day_bounds(day)
    uploaded = db.execute(select(Video.id, Video.created_at)
                          .where(Video.created_at >= start, Video.created_at < end)).all()
    times: list[float] = []
    for vid, created in uploaded:
        nth = db.scalar(select(Event.ts).where(Event.video_id == vid, Event.kind.in_(VIEW_KINDS))
                        .order_by(Event.ts, Event.id).offset(reach - 1).limit(1))
        if nth is not None:
            times.append((nth - created).total_seconds() * 1000)
    return int(statistics.median(times)) if times else None


def format_summary(row: MetricsDaily) -> str:
    f = lambda v: "-" if v is None else f"{v:.2f}"   # noqa: E731
    return "\n".join([
        f"metrics_daily {row.day}",
        f"  dau                 {row.dau}",
        f"  d1 / d7 / d30       {f(row.d1)} / {f(row.d7)} / {f(row.d30)}      (north star: d7)",
        f"  regret_proxy        {f(row.regret_proxy)}   sessions >20 min ending mid-video   [guardrail]",
        f"  long_session_share  {f(row.long_session_share)}   sessions >45 min                    [guardrail]",
        f"  median_ms_to_200    {'-' if row.median_ms_to_200 is None else row.median_ms_to_200}",
    ])


def _share(part: list, whole: list) -> float | None:
    return len(part) / len(whole) if whole else None
