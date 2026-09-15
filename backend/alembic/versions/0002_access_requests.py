"""Access-request domain, sessions and audit tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_access_requests"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
    )
    op.alter_column("users", "password_hash", server_default=None)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sessions_token_hash"), "sessions", ["token_hash"], unique=True)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    op.create_table(
        "access_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("employee_identifier", sa.String(length=128), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("job_role", sa.String(length=128), nullable=True),
        sa.Column("unit", sa.String(length=128), nullable=True),
        sa.Column("target_system", sa.String(length=64), nullable=True),
        sa.Column("requested_access_role", sa.String(length=128), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_proposal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_access_requests_owner_id"), "access_requests", ["owner_id"], unique=False
    )
    op.create_index(op.f("ix_access_requests_status"), "access_requests", ["status"], unique=False)

    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False),
        sa.Column("excerpts", postgresql.JSONB(), nullable=False),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=False),
        sa.Column("rule_violations", postgresql.JSONB(), nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.Column("source_references", postgresql.JSONB(), nullable=False),
        sa.Column("downstream_payload", postgresql.JSONB(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["access_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "revision", name="uq_proposals_request_revision"),
    )
    op.create_index(op.f("ix_proposals_request_id"), "proposals", ["request_id"], unique=False)
    op.create_index(op.f("ix_proposals_payload_hash"), "proposals", ["payload_hash"], unique=False)

    op.create_foreign_key(
        "fk_access_requests_current_proposal",
        "access_requests",
        "proposals",
        ["current_proposal_id"],
        ["id"],
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["access_requests.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approvals_proposal_id"), "approvals", ["proposal_id"], unique=False)
    op.create_index(op.f("ix_approvals_request_id"), "approvals", ["request_id"], unique=False)
    op.create_index(
        "uq_approvals_proposal_approve",
        "approvals",
        ["proposal_id"],
        unique=True,
        postgresql_where=sa.text("decision = 'approve'"),
    )

    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("approved_proposal_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("downstream_reference", sa.String(length=128), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approved_proposal_id"], ["proposals.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["access_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_submissions_approved_proposal_id"), "submissions", ["approved_proposal_id"]
    )
    op.create_index(op.f("ix_submissions_request_id"), "submissions", ["request_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["access_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"])
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"])
    op.create_index(op.f("ix_audit_events_request_id"), "audit_events", ["request_id"])
    op.create_index(op.f("ix_audit_events_correlation_id"), "audit_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("submissions")
    op.drop_index("uq_approvals_proposal_approve", table_name="approvals")
    op.drop_table("approvals")
    op.drop_constraint("fk_access_requests_current_proposal", "access_requests", type_="foreignkey")
    op.drop_table("proposals")
    op.drop_table("access_requests")
    op.drop_table("sessions")
    op.drop_column("users", "password_hash")
