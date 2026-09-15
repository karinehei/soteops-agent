import json
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "identities.json"


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
