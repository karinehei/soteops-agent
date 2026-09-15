from sqlalchemy import inspect, text

from app.core.db import create_db_engine
from tests.conftest import TEST_SETTINGS

REQUIRED_TABLES = {
    "alembic_version",
    "organizations",
    "users",
    "access_targets",
    "sessions",
    "access_requests",
    "proposals",
    "approvals",
    "submissions",
    "audit_events",
}


def test_pgvector_and_identity_tables_exist_after_migrations() -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    try:
        with engine.connect() as connection:
            extension = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
            tables = set(inspect(connection).get_table_names())
        assert extension == "vector"
        assert REQUIRED_TABLES <= tables
    finally:
        engine.dispose()
