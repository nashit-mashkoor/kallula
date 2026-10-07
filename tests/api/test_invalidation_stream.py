import asyncio
from datetime import UTC, datetime, timedelta

from helpers import append_run_event, build_client, seed_run
from sqlalchemy import select

from api.stream import invalidation_stream
from persistence.db import create_db_engine, create_session_factory
from persistence.events import append_event
from persistence.models import Run


def test_stream_requires_authentication(database_url):
    with build_client(database_url, development_mode=False) as test_client:
        response = test_client.get("/api/v1/stream")

    assert response.status_code == 401


def test_invalidation_stream_emits_resource_changed(database_url):
    run_id = seed_run(database_url)
    append_run_event(database_url, run_id, "first")

    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            cursor = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
            stream = invalidation_stream(factory, cursor, poll_interval=0.05)
            first = await asyncio.wait_for(stream.__anext__(), timeout=5)
            await stream.aclose()
        finally:
            await engine.dispose()
        return first

    first = asyncio.run(scenario())
    assert "event: resource_changed" in first
    assert f'"resource_id": "{run_id}"' in first
    assert '"reason": "STATE_CHANGED"' in first


def test_invalidation_stream_resumes_from_cursor(database_url):
    run_id = seed_run(database_url)
    append_run_event(database_url, run_id, "first")

    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            cursor = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
            stream = invalidation_stream(factory, cursor, poll_interval=0.05)
            first = await asyncio.wait_for(stream.__anext__(), timeout=5)
            assert f'"resource_id": "{run_id}"' in first
            first_cursor = first.split("id: ", 1)[1].split("\n", 1)[0]

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                await append_event(
                    session,
                    run,
                    event_type="RUN_STARTED",
                    category="RUN",
                    summary="second",
                )
                await session.commit()

            resumed = invalidation_stream(
                factory, datetime.fromisoformat(first_cursor), poll_interval=0.05
            )
            second = await asyncio.wait_for(resumed.__anext__(), timeout=5)
            assert f'"resource_id": "{run_id}"' in second
            assert datetime.fromisoformat(
                second.split("id: ", 1)[1].split("\n", 1)[0]
            ) > datetime.fromisoformat(first_cursor)

            await stream.aclose()
            await resumed.aclose()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
