FROM python:3.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock .python-version ./
COPY backend ./backend
COPY mock-integration ./mock-integration

RUN uv sync --locked --package soteops-mock-integration --no-dev

WORKDIR /app/mock-integration
EXPOSE 8001
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "mock_integration.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
