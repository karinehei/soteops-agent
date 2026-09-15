from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Session as AuthSession
from app.models import User

SESSION_COOKIE = "soteops_session"
CSRF_COOKIE = "soteops_csrf"
CSRF_HEADER = "X-CSRF-Token"


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user_id: UUID, settings: Settings) -> tuple[AuthSession, str]:
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    record = AuthSession(
        token_hash=hash_session_token(raw_token),
        user_id=user_id,
        csrf_token=csrf_token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(record)
    db.flush()
    return record, raw_token


def get_session_by_token(db: Session, token: str) -> AuthSession | None:
    record = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
    )
    if record is None:
        return None
    if record.expires_at <= datetime.now(UTC):
        db.delete(record)
        db.flush()
        return None
    return record


def set_auth_cookies(
    response: Response,
    settings: Settings,
    raw_token: str,
    csrf_token: str,
) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    _ = settings


def load_user(db: Session, session_record: AuthSession) -> User | None:
    return db.get(User, session_record.user_id)
