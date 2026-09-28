# VIBO – project rules for Claude Code

## What this is
A short-video feed (TikTok-style) whose recommender optimizes **D7/D30 retention**, not minutes-per-day. Read `ARCHITECTURE.md` and `docs/tiktok_weaknesses.md` before touching ranking logic. The ranker in `engine/` is the core; everything else is plumbing around it.

## Non-negotiables
- The ranker stays a pure Python package with zero I/O and zero external deps. Storage adapters live outside it.
- Every ranking decision must be explainable: `rank()` returns per-item score breakdowns, never just an ordered list.
- Exploration share (`EXPLORE_SHARE`) never drops below 0.10.
- No location, contacts, or device-fingerprint signals. In-app behavior only.
- `regret_proxy` and `long_session_share` are guardrail metrics; a change that improves watch time but worsens either is rejected.
- Trail (`trails` table) must be written for every session that had ≥1 completion. A session that leaves no trail is a ranking bug.

## Stack
- Python 3.11, FastAPI, Postgres, Redis, RQ workers. Tests with pytest.
- Mobile: Expo (React Native), TypeScript. Vertical pager, prefetch next 3 videos.
- Video: S3 + CloudFront, ffmpeg transcode to HLS 720p/480p.

## Conventions
- `engine/` = ranker + models + simulation. `api/` = FastAPI. `worker/` = aggregation jobs. `app/` = Expo.
- Events are append-only. Never mutate `events`; derive everything into `video_stats` / `user_profiles`.
- Run `python -m engine.demo` after any ranker change and paste the retention table in the PR description.
- Keep functions under 40 lines; if the ranker needs more, split the signal into its own function in `engine/signals.py`.

## Definition of done for a feature
1. Tests pass (`pytest`).
2. `engine.demo` retention did not regress.
3. If it touches the feed: a one-paragraph note in `docs/CHANGELOG.md` explaining the user-facing effect.
