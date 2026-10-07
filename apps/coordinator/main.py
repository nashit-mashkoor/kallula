import asyncio
import logging
import os
import signal

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine

from coordinator.loop import (
    POLL_INTERVAL_SECONDS,
    default_holder_id,
    process_queued_runs,
)
from observability.logging import configure_logging
from persistence.db import check_database, create_db_engine, create_session_factory

logger = logging.getLogger("coordinator")

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./kallula.db"


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
    load_dotenv()
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    engine = await start(database_url)
    factory = create_session_factory(engine)
    holder_id = default_holder_id()
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    logger.info("coordinator ready")

    try:
        while not stop.is_set():
            try:
                async with factory() as session:
                    processed = await process_queued_runs(session, holder_id=holder_id)
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
