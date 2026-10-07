import asyncio

from helpers import append_run_event, seed_run, trim_events
from sqlalchemy import select

from api.events import event_stream
from persistence.db import create_db_engine, create_session_factory
from persistence.events import append_event
from persistence.models import Run


def create_project(client, key="event-project"):
    response = client.post(
        "/api/v1/projects",
        json={"display_name": "Project"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def create_run(client, project_id, key="event-run"):
    response = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"objective": "Build it"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def test_event_list_and_after_sequence(client):
    project = create_project(client)
    run = create_run(client, project["id"])

    items = client.get(f"/api/v1/runs/{run['id']}/events").json()["items"]
    assert [item["sequence"] for item in items] == [1]
    assert items[0]["event_type"] == "RUN_QUEUED"
    assert items[0]["source"] == "CONTROL_PLANE"

    after = client.get(f"/api/v1/runs/{run['id']}/events?after_sequence=1").json()[
        "items"
    ]
    assert after == []


def test_event_list_rejects_unknown_severity(client):
    project = create_project(client, key="p-bad")
    run = create_run(client, project["id"], key="r-bad")

    response = client.get(f"/api/v1/runs/{run['id']}/events?severity=NOPE")

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_SEVERITY"


def test_event_stream_replays_existing_events(database_url):
    run_id = seed_run(database_url)
    append_run_event(database_url, run_id, "first")
    append_run_event(database_url, run_id, "second")

    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            stream = event_stream(factory, run_id, 0, poll_interval=0.05)
            first = await asyncio.wait_for(stream.__anext__(), timeout=5)
            second = await asyncio.wait_for(stream.__anext__(), timeout=5)
            assert "id: 1" in first
            assert "event: run_event" in first
            assert "id: 2" in second
            await stream.aclose()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_sse_returns_410_for_expired_cursor(client, database_url):
    run_id = seed_run(database_url)
    for index in range(4):
        append_run_event(database_url, run_id, f"event {index}")
    trim_events(database_url, run_id, keep_after_sequence=2)

    response = client.get(f"/api/v1/runs/{run_id}/events/stream?after_sequence=0")

    assert response.status_code == 410
    body = response.json()
    assert body["code"] == "EVENT_CURSOR_EXPIRED"
    assert body["earliest_available_sequence"] == 3
    assert body["last_event_sequence"] == 4


def test_event_stream_replays_then_delivers_live(database_url):
    run_id = seed_run(database_url)
    append_run_event(database_url, run_id, "first")

    async def scenario():
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            stream = event_stream(factory, run_id, 0, poll_interval=0.05)
            first = await asyncio.wait_for(stream.__anext__(), timeout=5)
            assert "id: 1" in first

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

            second = await asyncio.wait_for(stream.__anext__(), timeout=5)
            assert "id: 2" in second
            assert "RUN_STARTED" in second

            await stream.aclose()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
