from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


class ReadyCheck(BaseModel):
    database: str
    pgvector: str


class ReadyResponse(BaseModel):
    status: str
    checks: ReadyCheck


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
def ready(request: Request) -> ReadyResponse:
    engine = request.app.state.engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            extension = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "checks": {"database": "error", "pgvector": "unknown"},
            },
        ) from exc

    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "checks": {"database": "ok", "pgvector": "missing"}},
        )

    return ReadyResponse(
        status="ok",
        checks=ReadyCheck(database="ok", pgvector="ok"),
    )
