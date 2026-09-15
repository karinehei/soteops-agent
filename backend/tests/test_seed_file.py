import json
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "identities.json"
INSTRUCTIONS_PATH = Path(__file__).resolve().parents[2] / "seed" / "instructions.json"


def test_seed_identities_are_synthetic_and_complete() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(payload).lower()
    assert "potilas" not in serialized
    assert payload["organizations"]
    assert payload["access_targets"]
    roles = {user["role"] for user in payload["users"]}
    assert roles == {"requester", "reviewer", "operator"}
    for user in payload["users"]:
        assert user["email"].endswith("@demo.invalid")
        assert user["password"]
        assert "entra" not in user["password"].lower()


def test_instructions_are_synthetic_versioned_and_labelled() -> None:
    payload = json.loads(INSTRUCTIONS_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(payload).lower()
    assert "potilas" not in serialized
    assert "päijät" not in serialized
    documents = payload["documents"]
    topics = {topic for item in documents for topic in item["topics"]}
    assert {
        "permanent",
        "temporary",
        "unit-transfer",
        "missing-dates",
        "role-restrictions",
        "reviewer",
        "integration",
        "expired",
        "conflict",
    } <= topics
    ids = [item["document_id"] for item in documents]
    assert len(ids) == len(set(ids))
    expired = [item for item in documents if item["valid_to"] == "2023-12-31"]
    conflicting = [item for item in documents if "conflict" in item["topics"]]
    assert expired
    assert len(conflicting) >= 2
    for item in documents:
        assert item["synthetic_label"] == "SYNTHETIC"
        assert item["version"]
        assert item["valid_from"]
        assert "SYNTHETIC" in item["title"] or "SYNTHETIC" in item["body"]
