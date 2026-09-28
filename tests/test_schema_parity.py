"""engine/schema.sql is the source of truth. The SQLAlchemy models must mirror it column for column,
and the initial Alembic migration must be the schema file itself."""
from __future__ import annotations

import re
from pathlib import Path

from api.db.models import Base

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "engine" / "schema.sql").read_text()


def sql_tables() -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", SCHEMA, flags=re.S):
        cols = set()
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith(("PRIMARY KEY", "--")):
                continue
            cols.add(line.split()[0])
        tables[name] = cols
    return tables


def test_models_mirror_schema_sql():
    expected = sql_tables()
    got = {name: set(t.columns.keys()) for name, t in Base.metadata.tables.items()}
    assert got == expected


def test_initial_migration_executes_schema_sql():
    migration = (ROOT / "alembic" / "versions" / "0001_initial_schema.py").read_text()
    assert "schema.sql" in migration


def test_schema_has_no_location_or_contact_columns():
    forbidden = re.compile(r"\b(lat|lng|latitude|longitude|geo|gps|contacts?|phone|imei|fingerprint)\b", re.I)
    assert not forbidden.search(SCHEMA), "CLAUDE.md: in-app behavior only"


def test_later_migrations_take_ddl_from_schema_sql():
    import importlib.util
    path = ROOT / "alembic" / "versions" / "0002_reports_blocks.py"
    spec = importlib.util.spec_from_file_location("m0002", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ddl = m.table_ddl("reports")
    assert ddl.startswith("CREATE TABLE IF NOT EXISTS reports (") and "reason" in ddl and "--" not in ddl
