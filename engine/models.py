"""Data types shared by the ranker and the simulation. Storage adapters map DB rows to these."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class Video:
    id: int
    topics: dict[str, float]          # topic -> weight (sums ~1)
    duration_ms: int
    created_ts: float                 # epoch seconds
    sentiment: float = 0.0            # -1..1
    series_id: int | None = None
    series_index: int | None = None
    # derived stats
    impressions: int = 0
    completions: int = 0
    watch_ratio_sum: float = 0.0

    @property
    def avg_watch_ratio(self) -> float:
        return self.watch_ratio_sum / self.impressions if self.impressions else 0.0

    @property
    def completion_rate(self) -> float:
        return self.completions / self.impressions if self.impressions else 0.0


@dataclass
class Event:
    video_id: int
    kind: str                         # watch | swipe | rewatch | share | save
    watch_ratio: float                # 0..1+ (rewatch can exceed 1)
    topics: dict[str, float]
    ts: float


@dataclass
class UserProfile:
    """Long-term taste. Weights decay with a 7-day half-life applied on read."""
    user_id: int
    topics: dict[str, float] = field(default_factory=dict)
    last_update_ts: float = field(default_factory=time.time)
    seen: set[int] = field(default_factory=set)
    series_progress: dict[int, int] = field(default_factory=dict)   # series_id -> last index watched

    HALF_LIFE_S = 7 * 24 * 3600

    def decayed_topics(self, now: float) -> dict[str, float]:
        dt = max(0.0, now - self.last_update_ts)
        f = 0.5 ** (dt / self.HALF_LIFE_S)
        return {t: w * f for t, w in self.topics.items()}

    def apply(self, ev: Event, now: float) -> None:
        """Update taste from one event. Reward is centered: half-watch ~ neutral."""
        self.topics = self.decayed_topics(now)
        self.last_update_ts = now
        reward = _reward(ev)
        for t, w in ev.topics.items():
            self.topics[t] = self.topics.get(t, 0.0) + reward * w
        self.seen.add(ev.video_id)


@dataclass
class SessionState:
    """Short-term memory. Cleared after 30 min idle."""
    session_id: str
    events: list[Event] = field(default_factory=list)
    served: set[int] = field(default_factory=set)
    MAX_EVENTS = 20

    def push(self, ev: Event) -> None:
        self.events.append(ev)
        if len(self.events) > self.MAX_EVENTS:
            self.events.pop(0)

    def topic_fatigue(self) -> dict[str, float]:
        """Topics the user swiped early on, recently. 3 early swipes -> ~1.0 fatigue."""
        fat: dict[str, float] = {}
        for i, ev in enumerate(reversed(self.events[-8:])):
            if ev.kind == "swipe" and ev.watch_ratio < 0.3:
                recency = 0.8 ** i
                for t, w in ev.topics.items():
                    fat[t] = fat.get(t, 0.0) + 0.34 * w * recency
        return fat

    def recent_sentiment_run(self) -> int:
        """How many consecutive negative-sentiment items were just served."""
        n = 0
        for ev in reversed(self.events):
            if ev.topics.get("__sentiment__", 0.0) < -0.3:
                n += 1
            else:
                break
        return n


def _reward(ev: Event) -> float:
    if ev.kind == "share":
        return 2.0
    if ev.kind == "save":
        return 1.5
    if ev.kind == "rewatch":
        return 1.2
    # watch / swipe: map watch ratio to [-1, 1], neutral around 0.5
    return math.tanh((ev.watch_ratio - 0.5) * 3)
