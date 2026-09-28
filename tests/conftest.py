"""Shared fixtures. The API is exercised against SQLite + fakeredis so `pytest` needs no Docker.
Set TEST_DATABASE_URL / TEST_REDIS_URL to run the same suite against real Postgres + Redis."""
from __future__ import annotations

import os
import uuid

import fakeredis
import pytest
import redis as redis_lib
from fastapi.testclient import TestClient

from api.config import Settings
from api.db.models import Base
from api.main import create_app


@pytest.fixture
def redis_client():
    url = os.environ.get("TEST_REDIS_URL")
    r = redis_lib.Redis.from_url(url, decode_responses=True) if url else fakeredis.FakeRedis(decode_responses=True)
    r.flushdb()
    yield r
    r.flushdb()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/vibo.db"),
        redis_url="redis://unused",
        storage="local",
        media_dir=str(tmp_path / "media"),
        api_base="http://testserver",
        upload_secret="test-secret",
    )


@pytest.fixture
def app(settings, redis_client):
    application = create_app(settings, redis_client=redis_client)
    Base.metadata.drop_all(application.state.engine)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    with app.state.SessionLocal() as session:
        yield session


# ----------------------------------------------------------------------------- helpers

def new_session_id() -> str:
    return str(uuid.uuid4())


def create_video(client: TestClient, topic: str, *, sentiment: float = 0.0, duration_ms: int = 10_000,
                 series_id: int | None = None, series_index: int | None = None, upload: bool = True) -> dict:
    """POST /videos and, by default, complete the upload so the video is feed-eligible."""
    body = {"duration_ms": duration_ms, "topics": {topic: 1.0}, "sentiment": sentiment,
            "series_id": series_id, "series_index": series_index}
    created = client.post("/videos", json=body).json()
    created["duration_ms"] = duration_ms
    if upload:
        r = client.put(created["upload_url"], content=b"\x00\x00fakevideo", headers={"content-type": "video/mp4"})
        assert r.status_code == 200, r.text
    return created


def post_events(client: TestClient, user_id: str, session_id: str, events: list[dict]) -> dict:
    r = client.post("/events", json={"user_id": user_id, "session_id": session_id, "events": events})
    assert r.status_code == 200, r.text
    return r.json()


def watch(video: dict, ratio: float, kind: str = "watch", position: int = 0) -> dict:
    return {"video_id": video["video_id"], "kind": kind,
            "watch_ms": int(video["duration_ms"] * ratio), "position": position}
