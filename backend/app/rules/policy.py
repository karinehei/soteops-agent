from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RoleCombination(BaseModel):
    job_role: str
    access_role: str


class PolicyConfig(BaseModel):
    version: str
    required_fields: list[str]
    allowed_systems: list[str]
    allowed_job_roles: list[str]
    allowed_access_roles: list[str]
    allowed_employment_types: list[str]
    allowed_combinations: list[RoleCombination]
    temporary_access_roles: list[str]
    prohibited_access_roles: list[str]
    source: str = Field(default="seed/policy/v1.json")


def default_policy_path() -> Path:
    return Path(__file__).resolve().parents[3] / "seed" / "policy" / "v1.json"


def load_policy(path: Path | None = None) -> PolicyConfig:
    policy_path = path or default_policy_path()
    with policy_path.open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    policy = PolicyConfig.model_validate(payload)
    policy.source = str(policy_path.as_posix())
    return policy


@lru_cache(maxsize=8)
def current_policy(path: str | None = None) -> PolicyConfig:
    resolved = path or os.environ.get("POLICY_FILE") or str(default_policy_path())
    return load_policy(Path(resolved))
