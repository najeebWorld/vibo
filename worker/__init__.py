"""VIBO worker: RQ jobs that derive everything from the append-only events table.

  fold_stats        every 5 min   events -> video_stats
  compute_cohorts   hourly        k-means (k=8) on user topic vectors -> user_cohort, cohort_topic_scores
  daily_metrics     daily 00:10   D1/D7/D30, regret_proxy, long_session_share -> metrics_daily
"""
