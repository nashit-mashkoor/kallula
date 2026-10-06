from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kallula_api import health
from kallula_api.api import api_router
from kallula_api.db import create_engine
from kallula_api.logging import configure_logging
from kallula_api.problems import register_problem_handlers
from kallula_api.request_id import RequestIdMiddleware
from kallula_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.engine = create_engine(resolved_settings.database_url)
        try:
            yield
        finally:
            await app.state.engine.dispose()

    app = FastAPI(title="Kallula API", version="0.0.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.add_middleware(RequestIdMiddleware)
    register_problem_handlers(app)
    app.include_router(api_router)
    app.include_router(health.router)
    return app


app = create_app()
