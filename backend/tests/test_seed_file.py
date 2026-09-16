import json
from pathlib import Path

from app.core.paths import REPO_ROOT, resolve_repo_file
from app.seed import default_seed_path

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


def test_relative_seed_file_resolves_when_cwd_is_backend(monkeypatch) -> None:
    monkeypatch.chdir(REPO_ROOT / "backend")
    path = resolve_repo_file("seed/identities.json", "seed", "identities.json")
    assert path == default_seed_path().resolve()
    assert path.is_file()


def test_absolute_seed_file_is_kept(tmp_path) -> None:
    custom = tmp_path / "custom-identities.json"
    custom.write_text("{}", encoding="utf-8")
    path = resolve_repo_file(str(custom), "seed", "identities.json")
    assert path == custom
