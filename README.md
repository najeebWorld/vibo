# VIBO

A TikTok-style short-video feed whose recommender optimizes **retention (D7/D30)**, not minutes per day.
Phase 1 is complete: a pure ranker with a synthetic simulation, a FastAPI backend, an RQ worker, and an
Expo app for iOS and Android that a small group of friends can use daily.

## Quick start

```bash
# backend: postgres + redis + api + worker + cron, migrations, seed (200 videos, 30 users), first jobs
cp .env.example .env            # ports and API_BASE (for phones: your LAN IP, e.g. http://192.168.1.20:8010)
make dev
make test                       # pytest on SQLite + fakeredis, no Docker needed

# app: Expo Go on your phone (same Wi-Fi as the laptop)
cd app && cp .env.example .env && npm install --legacy-peer-deps && npx expo start
```

Swagger UI: `http://localhost:8010/docs` (port from `API_PORT` in `.env`).

## The ranker (phase 0)

Pure Python, no I/O, no dependencies. Every ranking decision returns a per-item score breakdown.

```bash
python -m engine.demo
```

Current result (200 synthetic users, 2,000 videos + 40 new per day, 30 days):

```
ranker            D1      D7     D30   new-video reach
random          0.57    0.60    0.64              0.16
popularity      0.52    0.62    0.65              0.05
vibo            0.66    0.85    0.82              0.68
```

Two lessons the simulation already taught:

1. **Content supply is part of the algorithm.** With only 600 videos, VIBO's D30 collapsed because users
   exhausted their favourite topics. A good ranker without enough fresh content is a trap.
2. **A retrieval stage is mandatory.** Scoring the whole catalog on every request does not scale even to
   2,000 videos. The ranker receives ~250 candidates; the API picks them (a random playable sample today).

## What is here

| Path | Role |
|---|---|
| `ARCHITECTURE.md` | Full architecture, development phases, metrics (Hebrew) |
| `CLAUDE.md` | Project rules that Claude Code reads automatically |
| `KICKOFF_PROMPT.md` | The prompt that produced phase 1 |
| `docs/tiktok_weaknesses.md` | 10 TikTok weaknesses (September 2026 research) and VIBO's fix for each (Hebrew) |
| `docs/CHANGELOG.md` | Every feed-facing change, with the user-visible effect and the retention table |
| `engine/schema.sql` | Postgres schema, the single source of truth for the data model |
| `engine/models.py` | Video / Event / UserProfile / SessionState |
| `engine/ranker.py` | The ranker: affinity, quality prior, cold start, 15% explore, topic fatigue, mood guard, series continuation |
| `engine/cohort.py` | Pure k-means + topic lift for the hourly cohort job |
| `engine/sim.py`, `engine/demo.py` | Synthetic world with hidden tastes; compares random / popularity / vibo |
| `api/` | FastAPI backend, see `api/README.md` |
| `worker/` | RQ jobs: stats fold, cohorts, daily metrics |
| `app/` | Expo app, see `app/README.md` (includes the store-readiness checklist) |
| `alembic/` | Migrations; 0001 applies `engine/schema.sql` verbatim |
| `tests/` | 94 backend tests; run them against real Postgres + Redis with `TEST_DATABASE_URL` / `TEST_REDIS_URL` |

## Backend (`api/`)

- `POST /events` (batch), `GET /feed?user_id&session_id&n=8`, `POST /videos` (presigned upload; local folder
  or S3 behind one interface), `GET /me/trail`, plus `POST /users`, report / block (store compliance for
  user-generated content) and the creator endpoints below.
- Postgres via SQLAlchemy; a test keeps the models equal to `engine/schema.sql` column for column.
- Redis: user topic profiles as a hash with a 7-day half-life applied on read; session state = last 20
  events with a 30-minute TTL.
- `user_id` accepts a numeric id or a device id (auto-created), since there is no login yet.
- Every session with at least one completion leaves a trail row (saved, series progress, topic unlocked,
  streak). That is the anti-emptiness feature.

## Worker (`worker/`)

`make dev` also starts `worker` (RQ) and `cron` (RQ's built-in scheduler).

- Every 5 minutes: events → `video_stats`.
- Hourly: k-means (k=8) on user topic vectors → `user_cohort`, `cohort_topic_scores`. This is what makes the
  ranker's `cohort` term non-zero.
- Daily at 00:10 UTC: D1/D7/D30 retention, `regret_proxy` (sessions over 20 min that ended mid-video) and
  `long_session_share` (sessions over 45 min) → `metrics_daily`, with a printed summary.

```bash
make jobs                    # run all three jobs now
DAY=2026-09-27 make metrics  # metrics for one day
make worker-logs
```

Metric definitions live in `worker/metrics.py` and `docs/CHANGELOG.md`.

## App (`app/`)

Expo SDK 57 + TypeScript, one codebase for iOS and Android. Expo Go for friends now, EAS Build for the stores.

- Vertical full-screen pager with sound, prefetch of the next 3 videos, event batcher every 5 s and on
  background, session renewal after 30 min away.
- A **chapter-end card** every 12 videos shows what the chapter added to your trail; the **Trail** screen
  lists everything you finished, saved or unlocked.
- Each video says *why* it is there, straight from the ranker's breakdown.
- Store readiness: first-launch terms, report with reasons, block creator, minimal permissions, no hardware
  identifiers (a random install id is the user id), dev-only network exceptions removed in production
  builds. Details and the submission checklist in `app/README.md`.

## Creator feedback

`GET /videos/{id}/retention` is computed live from events (it does not wait for the 5-minute fold): a
watch-ratio histogram in 10% buckets, a retention curve (share still watching at 0%, 10%, … 100%), and
where most viewers left. In the app: Trail → *My videos* → a video, or *Stats* in the ⋯ menu on your own
video. Refreshes every 30 s.

## Non-negotiables (from `CLAUDE.md`)

- The ranker stays pure: zero I/O, zero external dependencies.
- Exploration share never drops below 0.10.
- No location, contacts or device-fingerprint signals. In-app behavior only.
- `regret_proxy` and `long_session_share` are guardrails: a change that improves watch time but worsens
  either is rejected.

## Next

Phase 2: uploading from the phone, ffmpeg transcode to HLS, CloudFront. The upload endpoint, the storage
interface and the creator screen are already in place for it.
