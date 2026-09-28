"""App factory. Run: uvicorn --factory api.main:create_app"""
from __future__ import annotations

from pathlib import Path

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import Settings
from api.db.session import make_engine, make_sessionmaker
from api.routes import router
from api.storage import LocalStorage, S3Storage, Storage
from api.stores import ProfileStore, SessionStore


def build_storage(settings: Settings) -> Storage:
    if settings.storage == "s3":
        return S3Storage(settings.s3_bucket, settings.s3_region, settings.cdn_base, settings.upload_ttl_s)
    return LocalStorage(settings.media_dir, settings.api_base, settings.upload_secret, settings.upload_ttl_s)


def create_app(settings: Settings | None = None, redis_client: redis.Redis | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)
    r = redis_client or redis.Redis.from_url(settings.redis_url, decode_responses=True)

    app = FastAPI(title="VIBO API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = make_sessionmaker(engine)
    app.state.redis = r
    app.state.profiles = ProfileStore(r)
    app.state.sessions = SessionStore(r)
    app.state.storage = build_storage(settings)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    if isinstance(app.state.storage, LocalStorage):
        Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return app
