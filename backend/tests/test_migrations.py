from sqlalchemy import inspect, text

from app.core.db import create_db_engine
from app.models import Approval, Submission
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
    "instruction_documents",
    "instruction_chunks",
    "preparation_runs",
}


def test_approval_partial_unique_index_matches_migration() -> None:
    names = {index.name for index in Approval.__table__.indexes}
    assert "uq_approvals_proposal_approve" in names


def test_submission_outbox_columns_are_present() -> None:
    columns = {column.name for column in Submission.__table__.columns}
    assert {
        "approval_id",
        "payload_hash",
        "policy_version",
        "revision",
        "claimed_at",
        "last_attempt_at",
        "idempotency_key",
    } <= columns


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
