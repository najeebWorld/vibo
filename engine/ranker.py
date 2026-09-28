"""The ranker. Pure function of (profile, session, candidates, now) -> ranked items with score breakdown.

Design goals (see ARCHITECTURE.md):
- explainable: every item comes back with the contribution of each signal
- explore/exploit: EXPLORE_SHARE of slots go to high-quality items outside the user's profile
- session-aware: topic fatigue and mood guard use the last few events, not the last month
- cold start: new videos get a guaranteed exposure bonus until MIN_IMPRESSIONS
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .models import SessionState, UserProfile, Video

EXPLORE_SHARE = 0.15          # never below 0.10 (CLAUDE.md)
MIN_IMPRESSIONS = 200         # cold-start exposure quota
MAX_NEGATIVE_RUN = 2          # mood guard: at most 2 negative items in a row
FRESH_HALF_LIFE_S = 3 * 24 * 3600

WEIGHTS = {
    "affinity": 1.0,
    "quality": 0.8,
    "cohort": 0.6,
    "fresh": 0.3,
    "cold_start": 0.5,
    "series": 0.9,
    "fatigue": -1.2,
    "noise": 0.15,
}


@dataclass
class Scored:
    video: Video
    score: float
    breakdown: dict[str, float]
    slot: str   # "exploit" | "explore" | "series"


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _score_one(
    v: Video,
    taste: dict[str, float],
    fatigue: dict[str, float],
    cohort_scores: dict[str, float],
    now: float,
    rng: random.Random,
) -> Scored:
    b: dict[str, float] = {}
    b["affinity"] = WEIGHTS["affinity"] * _cosine(taste, v.topics)
    # quality prior: Bayesian-smoothed completion rate so 3/3 doesn't beat 180/200
    b["quality"] = WEIGHTS["quality"] * ((v.completions + 2) / (v.impressions + 5))
    b["cohort"] = WEIGHTS["cohort"] * sum(cohort_scores.get(t, 0.0) * w for t, w in v.topics.items())
    b["fresh"] = WEIGHTS["fresh"] * 0.5 ** ((now - v.created_ts) / FRESH_HALF_LIFE_S)
    b["cold_start"] = WEIGHTS["cold_start"] * max(0.0, 1 - v.impressions / MIN_IMPRESSIONS)
    b["fatigue"] = WEIGHTS["fatigue"] * sum(fatigue.get(t, 0.0) * w for t, w in v.topics.items())
    b["noise"] = WEIGHTS["noise"] * rng.gauss(0, 1)
    return Scored(v, sum(b.values()), b, "exploit")


def _next_in_series(profile: UserProfile, candidates: list[Video]) -> Video | None:
    """If the user is mid-series, the next episode is the strongest 'come back' signal we have."""
    for v in candidates:
        if v.series_id is None:
            continue
        last = profile.series_progress.get(v.series_id)
        if last is not None and v.series_index == last + 1:
            return v
    return None


def rank(
    profile: UserProfile,
    session: SessionState,
    candidates: list[Video],
    n: int = 8,
    now: float = 0.0,
    cohort_scores: dict[str, float] | None = None,
    seed: int | None = None,
) -> list[Scored]:
    rng = random.Random(seed)
    cohort_scores = cohort_scores or {}
    taste = profile.decayed_topics(now)
    fatigue = session.topic_fatigue()

    pool = [v for v in candidates if v.id not in profile.seen and v.id not in session.served]
    if not pool:
        return []

    out: list[Scored] = []

    # 1. series continuation gets slot 0 if available
    nxt = _next_in_series(profile, pool)
    if nxt is not None:
        s = _score_one(nxt, taste, fatigue, cohort_scores, now, rng)
        s.breakdown["series"] = WEIGHTS["series"]
        s.score += WEIGHTS["series"]
        s.slot = "series"
        out.append(s)
        pool = [v for v in pool if v.id != nxt.id]

    scored = [_score_one(v, taste, fatigue, cohort_scores, now, rng) for v in pool]
    scored.sort(key=lambda s: s.score, reverse=True)

    # 2. explore slots: low affinity, high quality
    n_explore = max(1, round(n * EXPLORE_SHARE))
    explore_pool = [s for s in scored if s.breakdown["affinity"] < 0.3 * WEIGHTS["affinity"]]
    explore_pool.sort(key=lambda s: s.breakdown["quality"] + s.breakdown["cold_start"], reverse=True)
    explore = explore_pool[:n_explore]
    for s in explore:
        s.slot = "explore"
    explore_ids = {s.video.id for s in explore}
    exploit = [s for s in scored if s.video.id not in explore_ids]

    # 3. interleave: exploit stream with explore items spread out
    merged: list[Scored] = []
    gap = max(1, (n - n_explore) // (n_explore + 1))
    ei = 0
    for i, s in enumerate(exploit):
        merged.append(s)
        if ei < len(explore) and (i + 1) % gap == 0:
            merged.append(explore[ei])
            ei += 1
    merged.extend(explore[ei:])

    # 4. mood guard: never more than MAX_NEGATIVE_RUN negatives in a row
    out.extend(apply_mood_guard(merged, session.recent_sentiment_run(), n - len(out)))
    for s in out:
        session.served.add(s.video.id)
    return out


def apply_mood_guard(items: list[Scored], run: int, n: int) -> list[Scored]:
    """Public so that feed-level reorderings (e.g. cold-start probes) can re-apply the same guard."""
    result: list[Scored] = []
    deferred: list[Scored] = []
    for s in items:
        if len(result) >= n:
            break
        neg = s.video.sentiment < -0.3
        if neg and run >= MAX_NEGATIVE_RUN:
            deferred.append(s)
            continue
        result.append(s)
        run = run + 1 if neg else 0
    # deferred negatives fill the tail only if there is nothing else, and never past the cap:
    # a short batch beats a doom run. The client simply asks for the next page.
    for s in deferred:
        if len(result) >= n or run >= MAX_NEGATIVE_RUN:
            break
        result.append(s)
        run += 1
    return result
