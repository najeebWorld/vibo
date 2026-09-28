"""Build DB + Redis handles from the environment for jobs that RQ invokes with no arguments."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import redis
from sqlalchemy.orm import Session

from api.config import Settings
from api.db.session import make_engine, make_sessionmaker
from api.stores import ProfileStore


@contextmanager
def job_context() -> Iterator[tuple[Session, ProfileStore]]:
    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        with make_sessionmaker(engine)() as db:
            yield db, ProfileStore(r)
    finally:
        engine.dispose()
