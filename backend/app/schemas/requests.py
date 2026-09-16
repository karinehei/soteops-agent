from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DemoFaultMode = Literal["success", "fail-before", "lost-response", "unavailable"]


class RequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(min_length=1)
    employee_identifier: str | None = None
    employment_type: str | None = None
    job_role: str | None = None
    unit: str | None = None
    target_system: str | None = None
    requested_access_role: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ApprovalAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    revision: int
    payload_hash: str
    policy_version: str
    comment: str | None = None


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class ForwardAction(BaseModel):
    """Optional local demo fault injection for mock-integration forwarding."""

    model_config = ConfigDict(extra="forbid")

    demo_fault: DemoFaultMode | None = None
