from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import SessionDep, SettingsDep
from app.auth.sessions import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    get_session_by_token,
    load_user,
)
from app.models import User

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def require_csrf(request: Request, db: SessionDep, settings: SettingsDep) -> None:
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER)
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid"
        )
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session:
        record = get_session_by_token(db, raw_session)
        if record is not None and not hmac.compare_digest(header, record.csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid"
            )
    _ = settings


def get_current_user(request: Request, db: SessionDep, settings: SettingsDep) -> User:
    if not settings.demo_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled outside local/demo configuration",
        )
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    record = get_session_by_token(db, token)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = load_user(db, record)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    request.state.auth_session = record
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CsrfDep = Annotated[None, Depends(require_csrf)]
