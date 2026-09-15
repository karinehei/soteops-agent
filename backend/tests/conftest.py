import os
import warnings
from collections.abc import Iterator
from pathlib import Path

warnings.filterwarnings("ignore", module=r"langgraph\..*")
warnings.filterwarnings("ignore", module=r"langchain_core\..*")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.sessions import CSRF_COOKIE, CSRF_HEADER
from app.core.config import Settings
from app.core.db import create_db_engine, create_session_factory
from app.main import create_app
from app.retrieval.ingest import (
    default_instructions_path,
    load_instructions_payload,
    seed_instructions,
)
from app.seed import default_seed_path, load_seed_payload, seed_identities

warnings.filterwarnings("ignore", message=".*allowed_objects.*")

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
)
os.environ.setdefault("MOCK_INTEGRATION_URL", "http://127.0.0.1:8001")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault(
    "POLICY_FILE",
    str(Path(__file__).resolve().parents[2] / "seed" / "policy" / "v1.json"),
)

TEST_SETTINGS = Settings(
    environment="test",
    log_level="INFO",
    database_url=os.environ["DATABASE_URL"],
    mock_integration_url="http://127.0.0.1:8001",
    cors_origins="http://127.0.0.1:3000",
    llm_provider="fake",
    embedding_provider="fake",
    ollama_base_url=None,
    seed_file="seed/identities.json",
    demo_auth_enabled=True,
    session_secret="test-session-secret",
    session_ttl_hours=12,
    cookie_secure=False,
    policy_file=str(Path(__file__).resolve().parents[2] / "seed" / "policy" / "v1.json"),
)

REQUESTER_EMAIL = "aino.esimerkki@demo.invalid"
SECOND_REQUESTER_EMAIL = "kaisa.esimerkki@demo.invalid"
REVIEWER_EMAIL = "ville.valvoja@demo.invalid"
SECOND_REVIEWER_EMAIL = "siiri.tarkastaja@demo.invalid"
OPERATOR_EMAIL = "outi.operaattori@demo.invalid"

VALID_REQUEST = {
    "original_text": (
        "Pyydän lukuoikeutta demo-hr-testi -järjestelmään synteettiselle työntekijälle EMP-1001. "
        "Rooli sairaanhoitaja, työsuhde vakituinen, yksikkö demo-osasto, alkaen 2026-10-01."
    ),
    "employee_identifier": "EMP-1001",
    "employment_type": "vakituinen",
    "job_role": "sairaanhoitaja",
    "unit": "demo-osasto",
    "target_system": "demo-hr-testi",
    "requested_access_role": "lukuoikeus",
    "start_date": "2026-10-01",
    "end_date": None,
}


def seed_passwords() -> dict[str, str]:
    payload = load_seed_payload(default_seed_path())
    return {item["email"]: item["password"] for item in payload["users"]}


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    if not token:
        token = client.get("/auth/csrf").json()["csrf_token"]
    return {CSRF_HEADER: str(token)}


def login(client: TestClient, email: str) -> None:
    password = seed_passwords()[email]
    headers = csrf_headers(client)
    response = client.post(
        "/auth/login", json={"email": email, "password": password}, headers=headers
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(TEST_SETTINGS)
    with TestClient(app) as test_client:
        yield test_client
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()


@pytest.fixture(scope="session")
def seed_demo_users() -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            seed_identities(session, load_seed_payload(default_seed_path()))
            seed_instructions(session, load_instructions_payload(default_instructions_path()))
            session.commit()
    finally:
        engine.dispose()


@pytest.fixture
def isolated_db(seed_demo_users: None) -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE audit_events, submissions, approvals, sessions, "
                    "preparation_runs, access_requests, proposals RESTART IDENTITY CASCADE"
                )
            )
    finally:
        engine.dispose()


@pytest.fixture
def domain_client(isolated_db: None) -> Iterator[TestClient]:
    app = create_app(TEST_SETTINGS)
    with TestClient(app) as test_client:
        yield test_client
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()
