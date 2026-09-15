from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from mock_integration.config import Settings, load_settings


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    stores_accounts: bool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.records = {}
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()
    app = FastAPI(
        title="SoteOps mock integration",
        summary="Stores synthetic request records. Does not provision accounts.",
        lifespan=lifespan,
    )
    app.state.settings = resolved

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="mock-integration")

    @app.get("/ready", response_model=ReadyResponse)
    def ready() -> ReadyResponse:
        return ReadyResponse(status="ok", stores_accounts=False)

    return app
