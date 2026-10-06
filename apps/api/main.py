from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import health
from api.problems import register_problem_handlers
from api.request_id import RequestIdMiddleware
from api.settings import Settings, get_settings
from api.v1 import api_router
from observability.logging import configure_logging
from persistence.db import create_db_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.db = create_db_engine(resolved_settings.database_url)
        try:
            yield
        finally:
            await app.state.db.dispose()

    app = FastAPI(title="Kallula API", version="0.0.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.add_middleware(RequestIdMiddleware)
    register_problem_handlers(app)
    app.include_router(api_router)
    app.include_router(health.router)
    return app


app = create_app()
