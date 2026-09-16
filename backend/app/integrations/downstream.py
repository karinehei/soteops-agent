from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.core.config import ALLOWED_FORWARD_HOSTS, Settings

IDEMPOTENCY_HEADER = "Idempotency-Key"
FAULT_HEADER = "X-Mock-Fault"


class DownstreamOutcome(StrEnum):
    ACCEPTED = "accepted"
    CONFLICT = "conflict"
    FAILED = "failed"
    UNKNOWN = "unknown"
    MISSING = "missing"


@dataclass(frozen=True)
class DownstreamResult:
    outcome: DownstreamOutcome
    record_id: str | None = None
    payload_hash: str | None = None
    status_code: int | None = None
    error_category: str | None = None


class DownstreamClient(Protocol):
    def post_request(
        self,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        fault: str | None = None,
    ) -> DownstreamResult: ...

    def get_request(self, idempotency_key: str) -> DownstreamResult: ...


def configured_destination(settings: Settings) -> str:
    url = str(settings.mock_integration_url).rstrip("/")
    host = urlparse(url).hostname
    if host not in ALLOWED_FORWARD_HOSTS:
        raise ValueError("forward destination is not in the configured allowlist")
    return url


class HttpDownstreamClient:
    """Calls only the configured mock-integration URL. Never logs payloads."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._base = configured_destination(settings)
        self._timeout = settings.forward_timeout_seconds
        self._client = client or httpx.Client(base_url=self._base, timeout=self._timeout)

    def post_request(
        self,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        fault: str | None = None,
    ) -> DownstreamResult:
        headers = {IDEMPOTENCY_HEADER: idempotency_key}
        if fault:
            headers[FAULT_HEADER] = fault
        try:
            response = self._client.post("/requests", json=payload, headers=headers)
        except httpx.TimeoutException:
            return DownstreamResult(outcome=DownstreamOutcome.UNKNOWN, error_category="timeout")
        except httpx.HTTPError:
            return DownstreamResult(
                outcome=DownstreamOutcome.FAILED, error_category="transport_error"
            )
        return _interpret_write(response, expected_hash=str(payload.get("payload_hash", "")))

    def get_request(self, idempotency_key: str) -> DownstreamResult:
        try:
            response = self._client.get(
                "/requests",
                params={"idempotency_key": idempotency_key},
            )
        except httpx.TimeoutException:
            return DownstreamResult(outcome=DownstreamOutcome.UNKNOWN, error_category="timeout")
        except httpx.HTTPError:
            return DownstreamResult(
                outcome=DownstreamOutcome.FAILED, error_category="transport_error"
            )
        if response.status_code == 404:
            return DownstreamResult(
                outcome=DownstreamOutcome.MISSING, status_code=404, error_category="not_found"
            )
        if response.status_code != 200:
            return DownstreamResult(
                outcome=DownstreamOutcome.UNKNOWN,
                status_code=response.status_code,
                error_category="lookup_error",
            )
        body = response.json()
        return DownstreamResult(
            outcome=DownstreamOutcome.ACCEPTED,
            record_id=str(body.get("record_id") or ""),
            payload_hash=str(body.get("payload_hash") or ""),
            status_code=200,
        )


def _interpret_write(response: httpx.Response, *, expected_hash: str) -> DownstreamResult:
    if response.status_code == 204:
        return DownstreamResult(
            outcome=DownstreamOutcome.UNKNOWN,
            status_code=204,
            error_category="lost_response",
        )
    if response.status_code == 409:
        return DownstreamResult(
            outcome=DownstreamOutcome.CONFLICT,
            status_code=409,
            error_category="idempotency_conflict",
        )
    if response.status_code in {200, 201}:
        body = response.json()
        record_id = str(body.get("record_id") or "")
        received_hash = str(body.get("payload_hash") or "")
        if not record_id or (expected_hash and received_hash != expected_hash):
            return DownstreamResult(
                outcome=DownstreamOutcome.UNKNOWN,
                status_code=response.status_code,
                error_category="incomplete_response",
            )
        return DownstreamResult(
            outcome=DownstreamOutcome.ACCEPTED,
            record_id=record_id,
            payload_hash=received_hash,
            status_code=response.status_code,
        )
    if response.status_code >= 500:
        return DownstreamResult(
            outcome=DownstreamOutcome.FAILED,
            status_code=response.status_code,
            error_category="downstream_5xx",
        )
    return DownstreamResult(
        outcome=DownstreamOutcome.FAILED,
        status_code=response.status_code,
        error_category="downstream_4xx",
    )


_OUTBOUND_FIELDS = (
    "employee_identifier",
    "target_system",
    "requested_access_role",
    "start_date",
    "end_date",
    "revision",
    "policy_version",
)


def outbound_payload(downstream_payload: dict[str, Any], payload_hash_value: str) -> dict[str, Any]:
    body = {key: downstream_payload.get(key) for key in _OUTBOUND_FIELDS}
    body["payload_hash"] = payload_hash_value
    return body
