FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
COPY apps/coordinator apps/coordinator
COPY packages packages

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "coordinator"]
