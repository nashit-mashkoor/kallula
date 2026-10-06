import asyncio
import logging
import os
import signal

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine

from observability.logging import configure_logging
from persistence.db import check_database, create_db_engine

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


async def _wait_for_stop() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    await stop.wait()


async def run() -> None:
    load_dotenv()
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    engine = await start(database_url)
    logger.info("coordinator ready")
    try:
        await _wait_for_stop()
    finally:
        await engine.dispose()
        logger.info("coordinator stopped")
