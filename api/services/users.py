from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import User


def resolve_user(db: Session, user_ref: str) -> int:
    """Accepts a numeric user id or a device id. Unknown device ids are created (no login in phase 1)."""
    if user_ref.isdigit():
        row = db.get(User, int(user_ref))
        if row is not None:
            return row.id
    row = db.scalar(select(User).where(User.device_id == user_ref))
    if row is None:
        row = User(device_id=user_ref)
        db.add(row)
        db.flush()
    return row.id
