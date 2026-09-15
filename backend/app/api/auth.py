from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import SessionDep, SettingsDep
from app.auth.deps import CsrfDep, CurrentUser
from app.auth.passwords import verify_password
from app.auth.sessions import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    clear_auth_cookies,
    create_session,
    get_session_by_token,
    set_auth_cookies,
)
from app.core.config import Settings
from app.models import User
from app.schemas.requests import LoginBody
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    role: str
    demo_authentication: bool = True
    identity_provider: str = "local-demo"
    note: str = "Demo authentication only. Not Entra ID or any production identity provider."


def _set_csrf_cookie(response: Response, settings: Settings, csrf_token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


@router.get("/csrf")
def issue_csrf(
    request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        record = get_session_by_token(db, token)
        if record is not None:
            _set_csrf_cookie(response, settings, record.csrf_token)
            return {
                "csrf_token": record.csrf_token,
                "note": "Demo CSRF cookie. Not Entra ID.",
            }
    csrf_token = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, settings, csrf_token)
    return {"csrf_token": csrf_token, "note": "Demo CSRF cookie. Not Entra ID."}


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    _: CsrfDep,
) -> MeResponse:
    if not settings.demo_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled outside local/demo configuration",
        )
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    record, raw_token = create_session(db, user.id, settings)
    record_audit(db, event_type="login", actor_id=user.id, request_id=None, metadata={})
    db.commit()
    set_auth_cookies(response, settings, raw_token, record.csrf_token)
    return MeResponse.model_validate(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    _: CsrfDep,
) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        record = get_session_by_token(db, token)
        if record is not None:
            record_audit(
                db, event_type="logout", actor_id=record.user_id, request_id=None, metadata={}
            )
            db.delete(record)
            db.commit()
    clear_auth_cookies(response, settings)
    return {"status": "logged_out"}


@router.get("/me")
def me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user)
