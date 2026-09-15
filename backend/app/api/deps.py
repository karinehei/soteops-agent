from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise TypeError("application settings are not configured")
    return settings


def get_session(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    if not isinstance(factory, sessionmaker):
        raise TypeError("database session factory is not configured")
    session = factory()
    try:
        yield session
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
