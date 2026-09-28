"""GET /feed: load state from Redis, candidates from Postgres, hand everything to engine.ranker.rank()."""
from __future__ import annotations

import zlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import Block, CohortTopicScore, UserCohort
from api.services.catalog import CatalogItem, load_items, main_topic
from api.stores import ProfileStore, SessionStore
from engine.ranker import Scored, apply_mood_guard, rank

PROBE_ITEMS = 8   # cold-start users: the first items span contrasting topics (ARCHITECTURE.md §1.6)


def build_feed(db: Session, profiles: ProfileStore, sessions: SessionStore, user_id: int, session_id: str,
               n: int, now: float, candidates: int = 250) -> list[tuple[Scored, CatalogItem]]:
    profile = profiles.load(user_id)
    session = sessions.load(session_id)
    items = load_items(db, exclude=profile.seen | session.served, exclude_creators=blocked_creators(db, user_id),
                       limit=candidates)
    seed = zlib.crc32(f"{session_id}:{len(session.served)}".encode())
    cold = not profile.topics
    ranked = rank(profile, session, [it.video for it in items.values()], n=n * 3 if cold else n, now=now,
                  cohort_scores=cohort_scores_for(db, user_id), seed=seed)
    if cold:
        # rank a wider slate, put one item per topic first, re-apply the guard, keep n.
        # Only what we actually return is marked served, so the rest stays eligible for the next page.
        ranked = apply_mood_guard(probe_order(ranked), session.recent_sentiment_run(), n)
    sessions.add_served(session_id, [s.video.id for s in ranked])
    return [(s, items[s.video.id]) for s in ranked]


def blocked_creators(db: Session, user_id: int) -> set[int]:
    return set(db.scalars(select(Block.blocked_user_id).where(Block.user_id == user_id)))


def cohort_scores_for(db: Session, user_id: int) -> dict[str, float]:
    cohort = db.scalar(select(UserCohort.cohort_id).where(UserCohort.user_id == user_id))
    if cohort is None:
        return {}
    rows = db.execute(select(CohortTopicScore.topic, CohortTopicScore.score)
                      .where(CohortTopicScore.cohort_id == cohort)).all()
    return {t: s for t, s in rows}


def probe_order(ranked: list[Scored]) -> list[Scored]:
    """A user with no taste yet gets one item per topic first, so the first swipes are informative.
    Pure reordering: scores and breakdowns are untouched, the slot says why the item is where it is."""
    head: list[Scored] = []
    tail: list[Scored] = []
    seen_topics: set[str] = set()
    for s in ranked:
        t = main_topic(s.video)
        if len(head) < PROBE_ITEMS and t not in seen_topics and s.slot != "series":
            seen_topics.add(t)
            s.slot = "probe"
            head.append(s)
        else:
            tail.append(s)
    return head + tail
