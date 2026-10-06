.PHONY: help migrate test lint format api coordinator web web-install web-test web-typecheck web-build dev compose-up compose-down

help:
	@echo "Kallula development commands"
	@echo ""
	@echo "  make migrate        Apply database migrations"
	@echo "  make test           Run backend tests"
	@echo "  make lint           Run backend lint and format checks"
	@echo "  make format         Format backend code"
	@echo "  make api            Start the API"
	@echo "  make coordinator    Start the coordinator"
	@echo "  make web-install    Install frontend dependencies"
	@echo "  make web            Start the frontend dev server"
	@echo "  make web-test       Run frontend tests"
	@echo "  make web-typecheck  Type-check the frontend"
	@echo "  make web-build      Build the frontend"
	@echo "  make dev            Start the full stack with Docker Compose"
	@echo "  make compose-up     Start the Docker Compose stack"
	@echo "  make compose-down   Stop the Docker Compose stack"

migrate:
	uv run alembic upgrade head

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

api:
	uv run uvicorn api.main:app --reload --port 8000

coordinator:
	uv run python -m coordinator

web-install:
	pnpm --dir apps/web install

web:
	pnpm --dir apps/web dev

web-test:
	pnpm --dir apps/web test

web-typecheck:
	pnpm --dir apps/web typecheck

web-build:
	pnpm --dir apps/web build

dev: compose-up

compose-up:
	docker compose up --build

compose-down:
	docker compose down
