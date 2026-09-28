"""Initial schema: applies engine/schema.sql verbatim (it is the source of truth).

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "engine" / "schema.sql"

TABLES = ["metrics_daily", "trails", "user_cohort", "cohort_topic_scores", "video_stats",
          "events", "video_topics", "videos", "users"]


def statements(sql: str) -> list[str]:
    """Split on ';' after stripping '--' comments (the header comment contains a ';')."""
    code = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [s.strip() for s in code.split(";") if s.strip()]


def upgrade() -> None:
    for statement in statements(SCHEMA_SQL.read_text()):
        op.execute(statement)


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
