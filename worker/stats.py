"""Every 5 minutes: fold events into video_stats. The aggregation lives next to the API because the
seed uses it too; the worker owns the schedule."""
from __future__ import annotations

from api.services.stats import fold_events_into_stats as fold_stats

__all__ = ["fold_stats"]
