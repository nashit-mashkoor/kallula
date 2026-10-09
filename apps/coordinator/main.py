import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncEngine

from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.loop import (
    POLL_INTERVAL_SECONDS,
    default_holder_id,
    process_queued_runs,
)
from coordinator.settings import CoordinatorSettings
from observability.logging import configure_logging
from persistence.db import check_database, create_db_engine, create_session_factory

logger = logging.getLogger("coordinator")


async def start(database_url: str) -> AsyncEngine:
    engine = create_db_engine(database_url)
    try:
        await check_database(engine)
    except Exception:
        await engine.dispose()
        raise
    return engine


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass


async def run() -> None:
    settings = CoordinatorSettings()
    configure_logging(settings.log_level)

    engine = await start(settings.database_url)
    factory = create_session_factory(engine)
    holder_id = default_holder_id()
    engine_factory = build_engine_factory(settings)
    if engine_factory is None:
        logger.warning("engine execution is unavailable in this mode")
    else:
        try:
            async with factory() as session:
                installation = await register_pinned_installation(session, settings)
                await session.commit()
            logger.info(
                "pinned engine installation registered",
                extra={"installation_id": installation.id},
            )
        except Exception:
            logger.exception("engine installation registration failed")
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    logger.info("coordinator ready")

    try:
        while not stop.is_set():
            try:
                async with factory() as session:
                    processed = (
                        0
                        if engine_factory is None
                        else await process_queued_runs(
                            session,
                            holder_id=holder_id,
                            engine_factory=engine_factory,
                        )
                    )
                    if processed:
                        logger.info("processed runs", extra={"count": processed})
            except Exception:
                logger.exception("coordinator iteration failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL_SECONDS)
            except TimeoutError:
                pass
    finally:
        await engine.dispose()
        logger.info("coordinator stopped")
