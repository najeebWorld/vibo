"""RQ entrypoints (no arguments: RQ calls them from the cron schedule) and a CLI to run them now.

  python -m worker.jobs all --day today
  python -m worker.jobs metrics --day 2026-09-27
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from worker.cohorts import compute_cohorts
from worker.context import job_context
from worker.metrics import compute_daily_metrics, format_summary
from worker.stats import fold_stats


def fold_stats_job() -> int:
    with job_context() as (db, _):
        n = fold_stats(db)
    print(f"fold_stats: {n} videos updated")
    return n


def compute_cohorts_job() -> dict:
    with job_context() as (db, profiles):
        result = compute_cohorts(db, profiles)
    print(f"compute_cohorts: {result['users']} users -> {result['cohorts']} cohorts, "
          f"sizes={result['sizes']}, top_topics={result['top_topics']}")
    return result


def daily_metrics_job(day: str | None = None) -> dict:
    d = parse_day(day)
    with job_context() as (db, _):
        row = compute_daily_metrics(db, d)
        summary = format_summary(row)
    print(summary)
    return {"day": d.isoformat(), "dau": row.dau, "d1": row.d1, "d7": row.d7, "d30": row.d30,
            "regret_proxy": row.regret_proxy, "long_session_share": row.long_session_share}


def parse_day(day: str | None) -> date:
    """Default: yesterday UTC (the last complete day). 'today' is for dev/demo runs."""
    today = datetime.now(timezone.utc).date()
    if day in (None, "", "yesterday"):
        return today - timedelta(days=1)
    if day == "today":
        return today
    return date.fromisoformat(day)


def main() -> None:
    p = argparse.ArgumentParser(description="run worker jobs now")
    p.add_argument("job", choices=["fold", "cohorts", "metrics", "all"])
    p.add_argument("--day", default=None, help="YYYY-MM-DD | today | yesterday (default)")
    a = p.parse_args()
    if a.job in ("fold", "all"):
        fold_stats_job()
    if a.job in ("cohorts", "all"):
        compute_cohorts_job()
    if a.job in ("metrics", "all"):
        daily_metrics_job(a.day)


if __name__ == "__main__":
    main()
