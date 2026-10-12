import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from coordinator.active import ActiveRuns
from coordinator.commands import process_commands
from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.loop import (
    POLL_INTERVAL_SECONDS,
    EngineFactory,
    default_holder_id,
    process_queued_runs,
)
from coordinator.reconcile import reconcile
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


async def _drive_loop(
    session_factory: async_sessionmaker[AsyncSession],
    holder_id: str,
    engine_factory: EngineFactory,
    active: ActiveRuns,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            async with session_factory() as session:
                processed = await process_queued_runs(
                    session,
                    holder_id=holder_id,
                    engine_factory=engine_factory,
                    active=active,
                )
                if processed:
                    logger.info("processed runs", extra={"count": processed})
        except Exception:
            logger.exception("coordinator iteration failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _command_loop(
    session_factory: async_sessionmaker[AsyncSession],
    active: ActiveRuns,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            async with session_factory() as session:
                applied = await process_commands(session, active=active)
                if applied:
                    logger.info("applied commands", extra={"count": applied})
        except Exception:
            logger.exception("command iteration failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


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
    active = ActiveRuns()
    tasks: list[asyncio.Task] = []
    if engine_factory is not None:
        try:
            async with factory() as session:
                reconciled = await reconcile(session, engine_factory=engine_factory)
                if reconciled:
                    logger.info("reconciled runs", extra={"count": reconciled})
        except Exception:
            logger.exception("reconciliation failed")
        tasks.append(
            asyncio.create_task(
                _drive_loop(factory, holder_id, engine_factory, active, stop)
            )
        )
        tasks.append(asyncio.create_task(_command_loop(factory, active, stop)))
    logger.info("coordinator ready")

    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()
        logger.info("coordinator stopped")
