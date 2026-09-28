# הפרומפט לפתיחה ב-VS Code (Claude Code)

פתח את התיקייה `vibo/` ב-VS Code, הפעל את Claude Code, והדבק את הפרומפט הבא כמו שהוא (הוא באנגלית כי זה עובד טוב יותר עם הכלים; אפשר לענות לו בעברית).

---

```
You are working in the VIBO repo. Start by reading CLAUDE.md, ARCHITECTURE.md, docs/tiktok_weaknesses.md, and everything under engine/. Then run `python -m engine.demo` and confirm it works.

Context: I'm a full-stack developer building a short-video feed whose recommender optimizes for D7/D30 retention rather than minutes per day. The ranker in engine/ is a working phase-0 prototype with a synthetic simulation. Your job is to take it to phase 1: a runnable backend + a minimal Expo app that 20 friends can use daily.

Do this in order, and stop after each numbered step to show me what you built before moving on:

1. Tests. Add pytest coverage for engine/ranker.py: exploration share is respected, session fatigue lowers a topic after 3 early swipes, already-seen items never reappear in the same session, mood_guard never allows 3 consecutive negative-sentiment items, and rank() always returns a score breakdown per item.

2. Backend. Create api/ with FastAPI:
   - POST /events (batch), GET /feed?user_id&session_id&n=8, POST /videos (returns presigned S3 URL; stub S3 with a local folder behind an interface), GET /me/trail.
   - Postgres via SQLAlchemy using engine/schema.sql as source of truth. Alembic migration from it.
   - Redis for user topic profiles (hash with 7-day half-life decay applied on read) and session state (last 20 events, TTL 30 min).
   - docker-compose.yml with postgres, redis, api. `make dev` brings everything up and seeds 200 synthetic videos + 30 synthetic users from engine/sim.py.

3. Worker. worker/ with RQ: every 5 minutes fold events into video_stats; hourly compute cohorts (k-means on user topic vectors, k=8) into cohort_topic_scores; daily compute D1/D7/D30 retention, regret_proxy (sessions >20 min ending with an abrupt close), and long_session_share. Write metrics to a metrics table and print a summary.

4. Mobile. app/ with Expo + TypeScript: vertical full-screen pager, autoplay with sound, prefetch next 3, an event batcher that posts every 5s and on background, a Trail screen, and a "chapter end" card every 12 items showing what was added to the trail. No login yet: device id as user id.

5. Creator feedback. Endpoint + screen showing a video's retention curve (watch-ratio histogram at 10% buckets) within an hour of upload.

Rules: keep the ranker pure and dependency-free; never add location or contact signals; explain any weight you change in docs/CHANGELOG.md; run engine.demo after ranker changes and paste the retention table in your summary. Ask me before adding any external service beyond Postgres, Redis and S3.
```

---

## איך להמשיך אחרי זה
- אחרי שלב 4 אתה כבר יכול לתת לחברים גרסת Expo Go. זה הרגע לבדוק אם הם חוזרים ביום השני.
- כשיש ~2,000 משתמשים פעילים: "Implement collaborative filtering in engine/cohort.py using implicit ALS on the events table, and A/B it against the heuristic ranker with a 50/50 split keyed on user_id hash."
- אל תיגע ב-deep learning לפני שהניקוד הידני ו-ALS מפסידים ב-A/B.
