from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    REQUESTER = "requester"
    REVIEWER = "reviewer"
    OPERATOR = "operator"


class RequestStatus(StrEnum):
    SUBMITTED = "submitted"
    PREPARING = "preparing"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_REVIEW = "ready_for_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FORWARDING = "forwarding"
    FORWARDED = "forwarded"
    FORWARD_FAILED = "forward_failed"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FAILED = "failed"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    organization: Mapped[Organization] = relationship(back_populates="users")


class AccessTarget(Base):
    __tablename__ = "access_targets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user: Mapped[User] = relationship()


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    employee_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_access_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[RequestStatus] = mapped_column(String(32), nullable=False, index=True)
    current_proposal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("proposals.id", use_alter=True, name="fk_access_requests_current_proposal"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    owner: Mapped[User] = relationship()
    current_proposal: Mapped["Proposal | None"] = relationship(
        foreign_keys=[current_proposal_id],
        post_update=True,
    )


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("request_id", "revision", name="uq_proposals_request_revision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("access_requests.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    excerpts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    missing_fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    rule_violations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_references: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    downstream_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("proposals.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("access_requests.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(String(16), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewer: Mapped[User] = relationship()
    proposal: Mapped[Proposal] = relationship()


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    approved_proposal_id: Mapped[UUID] = mapped_column(ForeignKey("proposals.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("access_requests.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downstream_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("access_requests.id"), nullable=True, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
