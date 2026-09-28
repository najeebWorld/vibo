"""Synthetic world for testing rankers offline.

Users have a hidden true taste vector. A video's watch ratio is a noisy function of taste match.
Users come back tomorrow with probability that depends on how satisfying the last session was
(mean watch ratio, whether something was saved, whether they're mid-series). That is the retention
proxy every ranker is judged on. It is a toy, but it punishes the same things real users punish.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .models import Event, SessionState, UserProfile, Video

TOPICS = ["cooking", "fitness", "comedy", "music", "diy", "science", "travel", "gaming", "news", "art"]
DAY = 24 * 3600


@dataclass
class SimUser:
    profile: UserProfile
    true_taste: dict[str, float]
    p_return: float = 1.0
    days_active: list[int] = field(default_factory=list)


def make_videos(n: int, rng: random.Random, now: float) -> list[Video]:
    vids = []
    for i in range(n):
        k = rng.choice([1, 1, 2])
        ts = rng.sample(TOPICS, k)
        topics = {t: 1.0 / k for t in ts}
        series_id, idx = None, None
        if rng.random() < 0.15:
            series_id, idx = rng.randint(1, 20), rng.randint(0, 5)
        vids.append(
            Video(
                id=i,
                topics=topics,
                duration_ms=rng.randint(8000, 45000),
                created_ts=now - rng.random() * 30 * DAY,
                sentiment=rng.choice([0.4, 0.2, 0.0, -0.1, -0.6]) if "news" in topics else rng.uniform(-0.2, 0.6),
                series_id=series_id,
                series_index=idx,
            )
        )
    return vids


def make_users(n: int, rng: random.Random) -> list[SimUser]:
    users = []
    for i in range(n):
        fav = rng.sample(TOPICS, 2)
        taste = {t: (0.8 if t in fav else 0.05) for t in TOPICS}
        users.append(SimUser(UserProfile(user_id=i), taste))
    return users


def watch_ratio(user: SimUser, v: Video, rng: random.Random, fatigue: float) -> float:
    match = sum(user.true_taste.get(t, 0) * w for t, w in v.topics.items())
    base = 0.15 + 0.9 * match - 0.25 * fatigue
    return max(0.0, min(1.3, rng.gauss(base, 0.15)))


def run_session(user: SimUser, vids: list[Video], rank_fn, now: float, rng: random.Random, length: int = 16):
    session = SessionState(session_id=f"{user.profile.user_id}-{int(now)}")
    ratios: list[float] = []
    saved = False
    recent_topics: list[str] = []
    while len(ratios) < length:
        batch = rank_fn(user.profile, session, vids, 8, now)
        if not batch:
            break
        for s in batch:
            v = s.video
            # user-side topic fatigue: same main topic 3x in the last 4 items feels repetitive
            main = max(v.topics, key=v.topics.get)
            fatigue = recent_topics[-4:].count(main) / 4
            recent_topics.append(main)
            r = watch_ratio(user, v, rng, fatigue)
            kind = "swipe" if r < 0.5 else ("rewatch" if r > 1.0 else "watch")
            if r > 0.9 and rng.random() < 0.15:
                kind, saved = "save", True
            topics = dict(v.topics)
            topics["__sentiment__"] = v.sentiment
            ev = Event(v.id, kind, r, topics, now)
            user.profile.apply(Event(v.id, kind, r, v.topics, now), now)
            session.push(ev)
            v.impressions += 1
            v.watch_ratio_sum += min(r, 1.0)
            if r >= 0.9:
                v.completions += 1
            if v.series_id is not None and r >= 0.7:
                user.profile.series_progress[v.series_id] = v.series_index
            ratios.append(r)
            now += v.duration_ms / 1000 * min(r, 1.0)
            if len(ratios) >= length:
                break
    mean = sum(ratios) / len(ratios) if ratios else 0.0
    mid_series = any(i < 5 for i in user.profile.series_progress.values())
    return mean, saved, mid_series


def return_probability(mean_ratio: float, saved: bool, mid_series: bool) -> float:
    p = 0.55 + 0.9 * max(0.0, mean_ratio - 0.35)
    if saved:
        p += 0.06
    if mid_series:
        p += 0.05
    return min(0.97, p)


def simulate(rank_fn, n_users: int = 200, n_videos: int = 2000, days: int = 30, seed: int = 7) -> dict:
    rng = random.Random(seed)
    now = time.time()
    vids = make_videos(n_videos, rng, now)
    users = make_users(n_users, rng)
    for day in range(days):
        t = now + day * DAY
        for u in users:
            if day > 0 and rng.random() > u.p_return:
                continue
            u.days_active.append(day)
            mean, saved, mid = run_session(u, vids, rank_fn, t, rng)
            u.p_return = return_probability(mean, saved, mid)
        # fresh content arrives every day
        for i in range(40):
            nv = make_videos(1, rng, t)[0]
            nv.id = len(vids)
            nv.created_ts = t
            vids.append(nv)

    def retained(d: int) -> float:
        return sum(1 for u in users if d in u.days_active) / n_users

    new_videos = [v for v in vids if v.created_ts > now]
    cold = sum(1 for v in new_videos if v.impressions >= 20) / max(1, len(new_videos))
    return {"d1": retained(1), "d7": retained(7), "d30": retained(days - 1), "new_video_reach": cold}
