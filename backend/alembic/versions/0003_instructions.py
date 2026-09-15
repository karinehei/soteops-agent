"""Instruction corpus, proposal extras, and preparation-run tracking."""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_instructions"
down_revision: str | Sequence[str] | None = "0002_access_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proposals",
        sa.Column("clarification_draft", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("proposals", "clarification_draft", server_default=None)
    op.add_column(
        "proposals",
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("proposals", "provider_metadata", server_default=None)

    op.create_table(
        "instruction_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("synthetic_label", sa.String(length=64), nullable=False),
        sa.Column("applies_to_systems", postgresql.JSONB(), nullable=False),
        sa.Column("topics", postgresql.JSONB(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_instruction_documents_document_id"),
        "instruction_documents",
        ["document_id"],
        unique=True,
    )

    op.create_table(
        "instruction_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_pk", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.ForeignKeyConstraint(["document_pk"], ["instruction_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_pk", "chunk_index", name="uq_instruction_chunks_doc_index"),
    )
    op.create_index(
        op.f("ix_instruction_chunks_document_pk"), "instruction_chunks", ["document_pk"]
    )
    op.create_index(
        op.f("ix_instruction_chunks_source_id"), "instruction_chunks", ["source_id"], unique=True
    )

    op.create_table(
        "preparation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("current_node", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("provider_name", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("embedding_provider", sa.String(length=32), nullable=False),
        sa.Column("durable_resume", sa.Boolean(), nullable=False),
        sa.Column(
            "started_at",
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
        sa.ForeignKeyConstraint(["request_id"], ["access_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_preparation_runs_request_id"), "preparation_runs", ["request_id"])
    op.create_index(op.f("ix_preparation_runs_status"), "preparation_runs", ["status"])


def downgrade() -> None:
    op.drop_table("preparation_runs")
    op.drop_table("instruction_chunks")
    op.drop_table("instruction_documents")
    op.drop_column("proposals", "provider_metadata")
    op.drop_column("proposals", "clarification_draft")
