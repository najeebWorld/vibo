from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from api.config import Settings
from api.storage import Storage
from api.stores import ProfileStore, SessionStore


@dataclass
class Ctx:
    settings: Settings
    profiles: ProfileStore
    sessions: SessionStore
    storage: Storage


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.SessionLocal() as db:
        yield db


def get_ctx(request: Request) -> Ctx:
    st = request.app.state
    return Ctx(settings=st.settings, profiles=st.profiles, sessions=st.sessions, storage=st.storage)
