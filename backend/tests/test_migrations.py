from sqlalchemy import inspect, text

from app.core.db import create_db_engine
from tests.conftest import TEST_SETTINGS

REQUIRED_TABLES = {"alembic_version", "organizations", "users", "access_targets"}


def test_pgvector_and_identity_tables_exist_after_migrations() -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    with engine.connect() as connection:
        extension = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    assert extension == "vector"
    tables = set(inspect(engine).get_table_names())
    assert REQUIRED_TABLES <= tables
