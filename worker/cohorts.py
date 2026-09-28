"""Hourly: k-means (k=8) over decayed user topic vectors -> user_cohort + cohort_topic_scores."""
from __future__ import annotations

import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.db.models import CohortTopicScore, User, UserCohort
from api.stores import ProfileStore
from engine.cohort import kmeans, topic_lift

K = 8


def compute_cohorts(db: Session, profiles: ProfileStore, k: int = K, now: float | None = None) -> dict:
    now = now or time.time()
    ids: list[int] = []
    vectors: list[dict[str, float]] = []
    for uid in db.scalars(select(User.id).order_by(User.id)):
        taste = {t: w for t, w in profiles.topics(uid, now).items() if w > 0}
        if taste:                      # users with no positive taste yet are left unassigned
            ids.append(uid)
            vectors.append(taste)

    labels = kmeans(vectors, k=k, seed=0)
    lift = topic_lift(vectors, labels)

    db.execute(delete(UserCohort))
    db.execute(delete(CohortTopicScore))
    db.add_all([UserCohort(user_id=u, cohort_id=c) for u, c in zip(ids, labels)])
    db.add_all([CohortTopicScore(cohort_id=c, topic=t, score=s)
                for c, scores in lift.items() for t, s in scores.items()])
    db.commit()
    return {
        "users": len(ids),
        "cohorts": len(set(labels)),
        "sizes": {c: labels.count(c) for c in sorted(set(labels))},
        "top_topics": {c: sorted(s, key=s.get, reverse=True)[:3] for c, s in lift.items()},
    }
