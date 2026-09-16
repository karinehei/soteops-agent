"""Submission outbox columns and claim timestamps."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_forwarding"
down_revision: str | Sequence[str] | None = "0003_instructions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("approval_id", sa.Uuid(), nullable=True))
    op.add_column(
        "submissions",
        sa.Column("payload_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "submissions",
        sa.Column("policy_version", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "submissions",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("submissions", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "submissions", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_submissions_approval_id",
        "submissions",
        "approvals",
        ["approval_id"],
        ["id"],
    )
    op.create_index(op.f("ix_submissions_approval_id"), "submissions", ["approval_id"])
    op.create_index(op.f("ix_submissions_payload_hash"), "submissions", ["payload_hash"])
    op.alter_column("submissions", "payload_hash", server_default=None)
    op.alter_column("submissions", "policy_version", server_default=None)
    op.alter_column("submissions", "revision", server_default=None)
    op.alter_column("submissions", "approval_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_submissions_approval_id", "submissions", type_="foreignkey")
    op.drop_index(op.f("ix_submissions_payload_hash"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_approval_id"), table_name="submissions")
    op.drop_column("submissions", "last_attempt_at")
    op.drop_column("submissions", "claimed_at")
    op.drop_column("submissions", "revision")
    op.drop_column("submissions", "policy_version")
    op.drop_column("submissions", "payload_hash")
    op.drop_column("submissions", "approval_id")
