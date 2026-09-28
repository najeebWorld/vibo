# Changelog

Feed-facing changes only. Every entry says what the user will notice and why.

## 2026-09-28 – mood guard: a short batch beats a doom run

**What changed.** `_apply_mood_guard` in `engine/ranker.py` used to append every deferred
negative-sentiment item at the tail of the batch "if there was nothing else". With a pool that was
mostly negative that produced runs of 3 to 5 negative items in a row, which is exactly what
`MAX_NEGATIVE_RUN = 2` exists to prevent (weakness #8 in `docs/tiktok_weaknesses.md`). The tail fill
now stops as soon as adding another negative would exceed the cap. The batch may come back shorter
than `n`; the client already re-requests when 3 items remain, so the feed simply continues on the
next page with the run reset by whatever non-negative content is available.

**User-facing effect.** Never more than two consecutive negative items, even when the candidate pool
is all news. If literally nothing non-negative is available and the user just watched two negatives,
the feed returns an empty page rather than a third negative.

**Weights.** None changed.

**engine.demo** (unchanged versus phase 0; the sim never produces an all-negative pool):

```
ranker            D1      D7     D30   new-video reach
random          0.57    0.60    0.64              0.16
popularity      0.52    0.62    0.65              0.05
vibo            0.66    0.85    0.82              0.68
```

## 2026-09-28 – phase 1 backend: feed served over HTTP, cold-start probes

**What changed.** `api/` wraps the ranker in FastAPI. `GET /feed` loads the profile (Redis hash, 7-day
half-life applied on read) and session state (last 20 events, 30-minute TTL), pulls up to 250 random
playable candidates from Postgres, and calls `engine.ranker.rank()` unchanged. `POST /events` appends
rows, folds each taste event into the profile and session, and writes the trail.

**Cold-start probes (feed-level, not a ranker change).** A user with no taste yet gets the first items
one-per-topic (`slot: "probe"`, ARCHITECTURE.md §1.6). The ranker scores a 3× wider slate, the feed puts
one item per main topic first, re-applies the mood guard, and returns `n`. Scores and breakdowns are
untouched; only what is returned is marked served, so the rest stays eligible for the next page.

**Trail rules.** `save` → `saved`; series item watched ≥70% → `series_progress` (this is also what drives
the ranker's series slot); first completion in a topic → `topic_unlocked`; every completion bumps the
session's single `streak` row (distinct videos). The streak row is what guarantees CLAUDE.md's invariant
that a session with ≥1 completion always leaves a trail.

**User-facing effect.** New users see eight contrasting videos first instead of eight near-identical
high-quality ones. Everyone else sees exactly what phase 0 ranked. Videos are playable only after the
upload completes (`hls_url` is NULL until then), so a half-uploaded clip never reaches a feed.

**Weights.** None changed. `_apply_mood_guard` was made public as `apply_mood_guard` so the feed can
re-apply it after the probe reordering; behaviour is identical.

**engine.demo** unchanged (no ranker logic touched):

```
ranker            D1      D7     D30   new-video reach
random          0.57    0.60    0.64              0.16
popularity      0.52    0.62    0.65              0.05
vibo            0.66    0.85    0.82              0.68
```

## 2026-09-28 – phase 1 worker: cohort signal goes live, daily metrics

**What changed.** `worker/` runs three RQ jobs (`rq cron worker/cron.py` enqueues, `rq worker vibo` executes):
- every 5 min `fold_stats`: events → `video_stats` (the ranker's quality prior and cold-start quota now
  reflect real views instead of the seed snapshot);
- hourly `compute_cohorts`: k-means (k=8, k-means++ init, pure Python in `engine/cohort.py`) over the
  decayed user topic vectors → `user_cohort`, and per-cohort **topic lift** → `cohort_topic_scores`.
  Lift = cohort mean share of a topic minus the population mean, scaled so the cohort's top topic is 1.0;
  topics at or below the population mean are omitted. Users with no positive taste are left unassigned;
- daily 00:10 UTC `daily_metrics` for the previous day → `metrics_daily`, and prints a summary.

**User-facing effect.** The `cohort` term of the score (weight 0.6, unchanged) was always 0 in phase 0
because nothing wrote cohort scores. It is now non-zero: a user in the "cooking + art" cohort gets a
small boost on art videos even before they watched any art. Everything else is as before.

**Metric definitions** (`worker/metrics.py`):
- `dau`: distinct users with a taste event that UTC day.
- `d1/d7/d30`: of the users active on day−k, the share also active on `day` (activity-based return rate;
  with 20 friends who all join the same week this is more informative than sign-up cohorts).
- `regret_proxy` (guardrail): of sessions longer than 20 min, the share that ended mid-video, i.e. the last
  taste event is a swipe or a watch with ratio < 0.5. Sessions are derived from events by `session_id`.
- `long_session_share` (guardrail): share of sessions longer than 45 min.
- `median_ms_to_200`: of videos uploaded that day that reached 200 views, median ms from upload to the 200th.

**Weights.** None changed. The ranker was not touched, so `engine.demo` was not rerun.

## 2026-09-28 – phase 1 app + UGC compliance: report and block filter the feed

**What changed.** The Expo app (`app/`) is the first real client. For the stores' user-generated-content
rules (Apple 1.2, Google UGC policy) the API gained `POST /videos/{id}/report` and `POST /users/block`, with
two new tables in `engine/schema.sql` (`reports`, `blocks`, migration 0002). A reported video joins the
reporter's seen set in Redis, so it never comes back for them; a blocked creator's videos are excluded at
retrieval for the blocker. Neither affects anyone else's feed or any score. `GET /feed` items now include
`creator_id` so the client can offer "block creator".

**User-facing effect.** Report and Block act immediately and only for the person who used them. The app
shows a first-launch terms screen, a "why this video" line built from the ranker's breakdown, a chapter-end
card every 12 videos, and the Trail screen.

**Weights.** None changed. Ranker untouched; `engine.demo` not rerun.
