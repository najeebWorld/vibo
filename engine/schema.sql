-- VIBO core schema (Postgres). Events are append-only; everything else is derived.

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_id     TEXT UNIQUE
);

CREATE TABLE videos (
    id            BIGSERIAL PRIMARY KEY,
    creator_id    BIGINT REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms   INT NOT NULL,
    hls_url       TEXT,
    sentiment     REAL NOT NULL DEFAULT 0,        -- -1..1, from creator tag + classifier
    series_id     BIGINT,                          -- nullable: part of a multi-episode series
    series_index  INT
);

CREATE TABLE video_topics (
    video_id      BIGINT REFERENCES videos(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    weight        REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (video_id, topic)
);

-- One row per client event. Never updated.
CREATE TABLE events (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id),
    session_id    UUID NOT NULL,
    video_id      BIGINT NOT NULL REFERENCES videos(id),
    kind          TEXT NOT NULL,   -- impression | watch | swipe | rewatch | share | save | pause
    watch_ms      INT,             -- for watch/swipe: how long before leaving
    position      INT,             -- index within session
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON events (user_id, ts DESC);
CREATE INDEX ON events (video_id, ts DESC);
CREATE INDEX ON events (session_id);

-- Derived by worker every 5 min.
CREATE TABLE video_stats (
    video_id        BIGINT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
    impressions     INT NOT NULL DEFAULT 0,
    completions     INT NOT NULL DEFAULT 0,
    avg_watch_ratio REAL NOT NULL DEFAULT 0,
    shares          INT NOT NULL DEFAULT 0,
    saves           INT NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Derived hourly. Which topics each cohort over-indexes on.
CREATE TABLE cohort_topic_scores (
    cohort_id     INT NOT NULL,
    topic         TEXT NOT NULL,
    score         REAL NOT NULL,
    PRIMARY KEY (cohort_id, topic)
);

CREATE TABLE user_cohort (
    user_id       BIGINT PRIMARY KEY REFERENCES users(id),
    cohort_id     INT NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The "trail": what a session left behind. This is the anti-emptiness feature.
CREATE TABLE trails (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id),
    session_id    UUID NOT NULL,
    kind          TEXT NOT NULL,   -- saved | series_progress | topic_unlocked | streak
    ref_id        BIGINT,          -- video_id or series_id
    payload       JSONB,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON trails (user_id, ts DESC);

-- Daily metrics. North star = d7. Guardrails = regret_proxy, long_session_share.
CREATE TABLE metrics_daily (
    day                 DATE PRIMARY KEY,
    dau                 INT,
    d1                  REAL,
    d7                  REAL,
    d30                 REAL,
    regret_proxy        REAL,   -- share of sessions >20min ending in abrupt close
    long_session_share  REAL,   -- share of sessions >45min
    median_ms_to_200    BIGINT  -- creator side: median time for new video to hit 200 impressions
);

-- Store compliance for user-generated content (Apple 1.2 / Google UGC policy): report, block.
-- A reported video is hidden from the reporter; a blocked creator's videos are hidden from the blocker.
CREATE TABLE reports (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id),
    video_id      BIGINT NOT NULL REFERENCES videos(id),
    reason        TEXT NOT NULL,   -- spam | harassment | violence | sexual | misinformation | other
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE blocks (
    user_id         BIGINT NOT NULL REFERENCES users(id),
    blocked_user_id BIGINT NOT NULL REFERENCES users(id),
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, blocked_user_id)
);
