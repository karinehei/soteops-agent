from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FaultMode = Literal["success", "fail-before", "lost-response", "unavailable"]


class DownstreamRequest(BaseModel):
    """Synthetic access-request record. This is not an account."""

    model_config = ConfigDict(extra="forbid")

    employee_identifier: str | None = None
    target_system: str | None = None
    requested_access_role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    revision: int
    policy_version: str
    payload_hash: str = Field(min_length=64, max_length=64)


class RecordResponse(BaseModel):
    record_id: str
    idempotency_key: str
    payload_hash: str
    stores_accounts: bool = False


class ErrorResponse(BaseModel):
    error: str
    stores_accounts: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
