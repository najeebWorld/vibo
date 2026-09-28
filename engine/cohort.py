"""Cohorts: k-means over user topic vectors, and per-cohort topic lift. Pure Python, no deps.

The worker runs this hourly (k=8) and writes user_cohort + cohort_topic_scores; the ranker reads the
scores back through rank(cohort_scores=...). Phase 3 replaces this with collaborative filtering.
"""
from __future__ import annotations

import math
import random

Vector = dict[str, float]


def kmeans(vectors: list[Vector], k: int, seed: int = 0, iters: int = 25) -> list[int]:
    """Cluster L1-normalized taste vectors. Returns one label per input vector, labels are 0..m-1."""
    if not vectors:
        return []
    keys = sorted({t for v in vectors for t in v})
    pts = [_normalize([max(0.0, v.get(t, 0.0)) for t in keys]) for v in vectors]
    k = min(k, len(pts))
    centroids = _kmeans_pp_init(pts, k, random.Random(seed))
    labels = [-1] * len(pts)
    for _ in range(iters):
        new = [_nearest(p, centroids) for p in pts]
        if new == labels:
            break
        labels = new
        for c in range(k):
            members = [p for p, l in zip(pts, labels) if l == c]
            if members:
                centroids[c] = _mean(members)
    return _compact(labels)


def topic_lift(vectors: list[Vector], labels: list[int]) -> dict[int, dict[str, float]]:
    """Per cohort: how much each topic is over-represented vs. the whole population, scaled so the
    cohort's top topic is 1.0. Topics at or below the population mean are omitted."""
    shares = [_share(v) for v in vectors]
    if not shares:
        return {}
    topics = sorted({t for s in shares for t in s})
    glob = {t: sum(s.get(t, 0.0) for s in shares) / len(shares) for t in topics}
    out: dict[int, dict[str, float]] = {}
    for c in sorted(set(labels)):
        members = [s for s, l in zip(shares, labels) if l == c]
        lift = {t: sum(s.get(t, 0.0) for s in members) / len(members) - glob[t] for t in topics}
        top = max(lift.values(), default=0.0)
        out[c] = {t: v / top for t, v in lift.items() if v > 0 and top > 0}
    return out


# ----------------------------------------------------------------------------- helpers

def _share(v: Vector) -> Vector:
    pos = {t: w for t, w in v.items() if w > 0}
    total = sum(pos.values())
    return {t: w / total for t, w in pos.items()} if total else {}


def _normalize(x: list[float]) -> list[float]:
    s = sum(x)
    return [v / s for v in x] if s else x


def _dist2(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _nearest(p: list[float], centroids: list[list[float]]) -> int:
    return min(range(len(centroids)), key=lambda c: _dist2(p, centroids[c]))


def _mean(pts: list[list[float]]) -> list[float]:
    return [sum(col) / len(pts) for col in zip(*pts)]


def _kmeans_pp_init(pts: list[list[float]], k: int, rng: random.Random) -> list[list[float]]:
    """k-means++: each next centroid is drawn with probability ∝ squared distance to the nearest one,
    so identical users never waste two seeds and an obvious second group always gets one."""
    centroids = [pts[rng.randrange(len(pts))]]
    while len(centroids) < k:
        d2 = [min(_dist2(p, c) for c in centroids) for p in pts]
        total = sum(d2)
        if total <= 1e-12:
            centroids.append(pts[rng.randrange(len(pts))])
            continue
        r, acc = rng.random() * total, 0.0
        for p, d in zip(pts, d2):
            acc += d
            if acc >= r:
                centroids.append(p)
                break
    return centroids


def _compact(labels: list[int]) -> list[int]:
    remap: dict[int, int] = {}
    return [remap.setdefault(l, len(remap)) for l in labels]


def cosine(a: Vector, b: Vector) -> float:
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0
