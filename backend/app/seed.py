from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_settings
from app.core.db import create_db_engine, create_session_factory
from app.models import AccessTarget, Organization, User, UserRole

logger = logging.getLogger(__name__)


def default_seed_path() -> Path:
    return Path(__file__).resolve().parents[2] / "seed" / "identities.json"


def load_seed_payload(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Seed file must contain a JSON object")
    return payload


def seed_identities(session: Session, payload: dict[str, Any]) -> None:
    organizations = {item["slug"]: item for item in payload["organizations"]}
    slug_to_org: dict[str, Organization] = {}
    for slug, item in organizations.items():
        organization = session.scalar(select(Organization).where(Organization.slug == slug))
        if organization is None:
            organization = Organization(id=uuid4(), slug=slug, name=item["name"])
            session.add(organization)
        else:
            organization.name = item["name"]
        slug_to_org[slug] = organization
    session.flush()

    for item in payload["users"]:
        user = session.scalar(select(User).where(User.email == item["email"]))
        organization = slug_to_org[item["organization_slug"]]
        role = UserRole(item["role"])
        if user is None:
            session.add(
                User(
                    id=uuid4(),
                    email=item["email"],
                    display_name=item["display_name"],
                    role=role,
                    organization_id=organization.id,
                )
            )
        else:
            user.display_name = item["display_name"]
            user.role = role
            user.organization_id = organization.id

    for item in payload["access_targets"]:
        target = session.scalar(select(AccessTarget).where(AccessTarget.slug == item["slug"]))
        if target is None:
            session.add(AccessTarget(id=uuid4(), slug=item["slug"], name=item["name"]))
        else:
            target.name = item["name"]


def main() -> None:
    settings = load_settings()
    seed_path = Path(settings.seed_file) if settings.seed_file else default_seed_path()
    payload = load_seed_payload(seed_path)
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_identities(session, payload)
        session.commit()
    logger.info("Synthetic seed completed from %s", seed_path)


if __name__ == "__main__":
    main()
