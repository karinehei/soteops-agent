from __future__ import annotations

import json
from hashlib import sha256
from threading import Lock
from typing import Any
from uuid import uuid4

from mock_integration.schemas import DownstreamRequest, RecordResponse


def canonical_payload(payload: DownstreamRequest) -> dict[str, Any]:
    data = payload.model_dump()
    data.pop("payload_hash", None)
    return data


def compute_payload_hash(payload: DownstreamRequest) -> str:
    encoded = json.dumps(
        canonical_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


class UniqueStore:
    """Lock-protected uniqueness on idempotency_key for the process lifetime.

    Repeat puts with the same key and payload return the stored record. A different
    payload for an existing key is rejected. This does not create accounts.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, RecordResponse] = {}
        self._hashes: dict[str, str] = {}

    def put(self, idempotency_key: str, payload: DownstreamRequest) -> tuple[RecordResponse, bool]:
        expected = compute_payload_hash(payload)
        if payload.payload_hash != expected:
            raise ValueError("payload_hash does not match canonical payload")
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is None:
                record = RecordResponse(
                    record_id=str(uuid4()),
                    idempotency_key=idempotency_key,
                    payload_hash=expected,
                    stores_accounts=False,
                )
                self._records[idempotency_key] = record
                self._hashes[idempotency_key] = expected
                return record, True
            if self._hashes[idempotency_key] != expected:
                raise KeyError("idempotency_key_conflict")
            return existing, False

    def get(self, idempotency_key: str) -> RecordResponse | None:
        with self._lock:
            record = self._records.get(idempotency_key)
            return record.model_copy() if record is not None else None

    def snapshot(self) -> list[RecordResponse]:
        with self._lock:
            return [record.model_copy() for record in self._records.values()]

    def count(self) -> int:
        with self._lock:
            return len(self._records)
