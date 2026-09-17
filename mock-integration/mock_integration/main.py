from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mock_integration.config import Settings, load_settings
from mock_integration.schemas import DownstreamRequest, ErrorResponse, FaultMode, RecordResponse
from mock_integration.store import UniqueStore

DEMO_ENVIRONMENTS = frozenset({"local", "test", "ci"})
IDEMPOTENCY_HEADER = "Idempotency-Key"
FAULT_HEADER = "X-Mock-Fault"


class HealthOut(BaseModel):
    status: str
    service: str


class ReadyOut(BaseModel):
    status: str
    stores_accounts: bool


class RecordSummary(BaseModel):
    record_id: str
    idempotency_key: str
    stores_accounts: bool


class RecordsOut(BaseModel):
    count: int
    stores_accounts: bool
    records: list[RecordSummary]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.store = UniqueStore()
    yield


def _store(app: FastAPI) -> UniqueStore:
    store = app.state.store
    if not isinstance(store, UniqueStore):
        raise TypeError("mock store is not configured")
    return store


def _fault_mode(raw: str | None, settings: Settings) -> FaultMode:
    if not raw:
        return "success"
    if raw not in {"success", "fail-before", "lost-response", "unavailable"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown mock fault mode",
        )
    if settings.environment not in DEMO_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fault modes are local-only",
        )
    return raw  # type: ignore[return-value]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()
    app = FastAPI(
        title="SoteOps mock integration",
        summary="Stores synthetic request records. Does not provision accounts.",
        lifespan=lifespan,
    )
    app.state.settings = resolved

    @app.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(status="ok", service="mock-integration")

    @app.get("/ready", response_model=ReadyOut)
    def ready() -> ReadyOut:
        return ReadyOut(status="ok", stores_accounts=False)

    @app.get("/records", response_model=RecordsOut)
    def list_records() -> RecordsOut:
        """Local-only inventory for walkthrough assertions. Does not list payloads."""
        if resolved.environment not in DEMO_ENVIRONMENTS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        stored = _store(app).snapshot()
        return RecordsOut(
            count=len(stored),
            stores_accounts=False,
            records=[
                RecordSummary(
                    record_id=item.record_id,
                    idempotency_key=item.idempotency_key,
                    stores_accounts=item.stores_accounts,
                )
                for item in stored
            ],
        )

    @app.post(
        "/requests",
        response_model=RecordResponse,
        responses={
            204: {"description": "Record stored; response intentionally omitted"},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def create_request(
        payload: DownstreamRequest,
        idempotency_key: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER),
        fault: str | None = Header(default=None, alias=FAULT_HEADER),
    ) -> Response:
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Idempotency-Key is required",
            )
        mode = _fault_mode(fault, resolved)
        if mode == "fail-before":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Injected failure before processing",
            )
        if mode == "unavailable":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Injected temporary unavailability",
            )
        try:
            record, created = _store(app).put(idempotency_key.strip(), payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key reused with different payload",
            ) from None
        if mode == "lost-response":
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return JSONResponse(record.model_dump(), status_code=code)

    @app.get("/requests", response_model=RecordResponse)
    def lookup_request(idempotency_key: str = Query(min_length=1)) -> RecordResponse:
        record = _store(app).get(idempotency_key)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return record

    return app
