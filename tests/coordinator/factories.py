from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from engine.base import Engine
from persistence.models import Run


def static_factory(engine: Engine) -> Callable[[AsyncSession, Run], Awaitable[Engine]]:
    async def factory(session: AsyncSession, run: Run) -> Engine:
        return engine

    return factory
