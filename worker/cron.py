"""RQ cron schedule. Run:  rq cron worker/cron.py --url $REDIS_URL   (plus  rq worker vibo)"""
from __future__ import annotations

from rq import cron

from worker.jobs import compute_cohorts_job, daily_metrics_job, fold_stats_job

QUEUE = "vibo"

SCHEDULE = [
    {"name": "fold_stats", "func": fold_stats_job, "interval": 5 * 60},
    {"name": "compute_cohorts", "func": compute_cohorts_job, "interval": 60 * 60},
    {"name": "daily_metrics", "func": daily_metrics_job, "cron": "10 0 * * *"},   # 00:10 UTC, for yesterday
]

for s in SCHEDULE:
    cron.register(s["func"], QUEUE, interval=s.get("interval"), cron=s.get("cron"), name=s["name"],
                  job_timeout=10 * 60, result_ttl=24 * 3600)
