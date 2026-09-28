"""reports + blocks (UGC store compliance). DDL is taken from engine/schema.sql, applied IF NOT EXISTS
because a fresh database already gets these tables from 0001 (which applies the whole schema file).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""
from __future__ import annotations

import re
from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "engine" / "schema.sql"
TABLES = ["reports", "blocks"]


def table_ddl(name: str) -> str:
    sql = SCHEMA_SQL.read_text()
    m = re.search(rf"CREATE TABLE {name} \(.*?\n\);", sql, flags=re.S)
    assert m, f"{name} missing from schema.sql"
    body = "\n".join(line.split("--", 1)[0] for line in m.group(0).splitlines())
    return body.replace(f"CREATE TABLE {name}", f"CREATE TABLE IF NOT EXISTS {name}", 1).rstrip(";")


def upgrade() -> None:
    for t in TABLES:
        op.execute(table_ddl(t))


def downgrade() -> None:
    for t in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
