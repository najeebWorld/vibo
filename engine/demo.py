"""Run: python -m engine.demo
Compares three rankers on the synthetic world: random, popularity-only, and VIBO.
"""
from __future__ import annotations

import random

CANDIDATES = 250   # retrieval stage: rankers score a sample, not the whole catalog


def retrieve(profile: UserProfile, session: SessionState, vids: list[Video]) -> list[Video]:
    pool = [v for v in vids if v.id not in profile.seen and v.id not in session.served]
    rng = random.Random(len(profile.seen) * 31 + len(session.served))
    return pool if len(pool) <= CANDIDATES else rng.sample(pool, CANDIDATES)


from .models import SessionState, UserProfile, Video
from .ranker import Scored, rank
from .sim import simulate


def random_ranker(profile: UserProfile, session: SessionState, vids: list[Video], n: int, now: float):
    pool = retrieve(profile, session, vids)
    rng = random.Random(len(profile.seen))
    picks = rng.sample(pool, min(n, len(pool)))
    for v in picks:
        session.served.add(v.id)
    return [Scored(v, 0.0, {}, "random") for v in picks]


def popularity_ranker(profile: UserProfile, session: SessionState, vids: list[Video], n: int, now: float):
    pool = retrieve(profile, session, vids)
    pool.sort(key=lambda v: v.completion_rate, reverse=True)
    picks = pool[:n]
    for v in picks:
        session.served.add(v.id)
    return [Scored(v, v.completion_rate, {}, "popular") for v in picks]


def vibo_ranker(profile: UserProfile, session: SessionState, vids: list[Video], n: int, now: float):
    return rank(profile, session, retrieve(profile, session, vids), n=n, now=now, seed=len(profile.seen))


def main() -> None:
    rows = []
    for name, fn in [("random", random_ranker), ("popularity", popularity_ranker), ("vibo", vibo_ranker)]:
        r = simulate(fn)
        rows.append((name, r))
    print(f"{'ranker':<12}{'D1':>8}{'D7':>8}{'D30':>8}{'new-video reach':>18}")
    for name, r in rows:
        print(f"{name:<12}{r['d1']:>8.2f}{r['d7']:>8.2f}{r['d30']:>8.2f}{r['new_video_reach']:>18.2f}")
    print("\nnew-video reach = share of videos uploaded during the sim that got >=20 impressions")


if __name__ == "__main__":
    main()
