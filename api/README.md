# api/ – FastAPI around the pure ranker

```
make dev        # postgres + redis + api, migrations, seed (200 videos, 30 users)
make test       # pytest on SQLite + fakeredis (no Docker needed)
make jobs       # run the worker's fold / cohorts / metrics jobs now
make logs | make worker-logs | make psql | make redis-cli | make reset | make down
```
Ports and the public base URL come from `.env` (copy `.env.example`). Swagger UI: `http://localhost:$API_PORT/docs`.

Run the same tests against the real stack:
```
TEST_DATABASE_URL=postgresql+psycopg://vibo:vibo@localhost:55432/vibo_test \
TEST_REDIS_URL=redis://localhost:56379/1 make test
```
(`vibo_test` is created by `make dev`'s first run; if missing: `make psql` → `CREATE DATABASE vibo_test;`)

## Endpoints
| Method | Path | Notes |
|---|---|---|
| POST | `/users` | `{device_id}` → `{user_id}`. Every `user_id` param below accepts a numeric id **or** a device id (auto-created). |
| GET | `/feed?user_id&session_id&n=8` | `session_id` is a UUID minted by the client. Items carry `score`, `slot`, `breakdown`. |
| POST | `/events` | `{user_id, session_id, events:[{video_id, kind, watch_ms?, position?, ts?}]}`. Returns the trail entries the batch created. |
| POST | `/videos` | `{duration_ms, topics, sentiment?, series_id?, series_index?, creator_id?}` → `{video_id, upload_url}`. PUT the file to `upload_url`. |
| POST | `/videos/{id}/complete` | S3 clients call this after the PUT. Local storage does it automatically. |
| GET | `/me/trail?user_id&session_id?&since?&limit?` | Newest first. `session_id` scopes it to one session (chapter-end card). |
| POST | `/videos/{id}/report` | `{user_id, reason}`; the video is hidden from that user immediately (UGC compliance). |
| POST | `/users/block` | `{user_id, blocked_user_id}`; the creator's videos never reach the blocker's feed. Idempotent. |
| GET | `/videos/{id}/retention` | Creator feedback, live from events: `histogram` (10 buckets of watch ratio), `retention` (11 points, share still watching at k·10%), `completion_rate`, `biggest_drop`. |
| GET | `/me/videos?user_id` | The creator's uploads, newest first, with live views / completion. |
| GET | `/health` | `{ok, db, redis}` |

Event kinds: `impression | watch | swipe | rewatch | share | save | pause`. `watch_ms` is how long the
user stayed; watch ratio = `watch_ms / duration_ms` (capped at 1.3). `impression`/`pause` are logged but do
not move the taste profile.

## Layout
```
api/main.py            app factory (uvicorn --factory api.main:create_app)
api/routes.py          HTTP layer only
api/services/feed.py   Redis + Postgres → engine.ranker.rank() → served ids
api/services/ingest.py POST /events: events rows, profile, session, trail
api/services/trail.py  trail rules (see docs/CHANGELOG.md)
api/services/stats.py  events → video_stats (worker will own the schedule)
api/stores.py          Redis adapters ⇄ engine.models.UserProfile / SessionState
api/storage.py         Storage protocol: LocalStorage (dev) / S3Storage (STORAGE=s3)
api/db/models.py       SQLAlchemy models; tests/test_schema_parity.py keeps them equal to engine/schema.sql
alembic/               0001 applies engine/schema.sql verbatim. New columns: edit schema.sql, add a migration.
api/seed.py            engine/sim.py users + videos, pushed through the real ingest path
```

## Storage
`STORAGE=local` (default): files under `MEDIA_DIR`, the "presigned URL" is an HMAC-signed PUT to this API,
served back from `/media/…`. `STORAGE=s3`: boto3 presigned PUT to `S3_BUCKET`, public URL via `CDN_BASE`.
Transcoding to HLS is phase 2; `hls_url` currently points at the source file.
