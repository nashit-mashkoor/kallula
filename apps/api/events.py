import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import get_principal_id, get_session
from api.problems import problem_response
from api.runs import owned_run
from domain.states import EventSeverity
from persistence.models import Event

router = APIRouter(tags=["events"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
POLL_INTERVAL_SECONDS = 0.5
KEEPALIVE_SECONDS = 15.0


def event_response(event: Event) -> dict:
    stage = None
    if event.stage_category is not None:
        stage = {
            "category": event.stage_category,
            "native_id": event.stage_native_id,
            "display_label": event.stage_label,
            "order": event.stage_order,
        }
    return {
        "id": event.id,
        "run_id": event.run_id,
        "sequence": event.sequence,
        "attempt_id": event.attempt_id,
        "source": event.source.value,
        "source_event_sequence": event.source_event_sequence,
        "event_type": event.event_type,
        "category": event.category,
        "severity": event.severity.value,
        "stage": stage,
        "work_item_id": event.work_item_id,
        "summary": event.summary,
        "payload_version": event.payload_version,
        "payload": event.payload_json,
        "artifact_ids": event.artifact_ids_json,
        "occurred_at": event.occurred_at.isoformat(),
        "recorded_at": event.recorded_at.isoformat(),
    }


def sse_frame(event: Event) -> str:
    data = json.dumps(event_response(event))
    return f"id: {event.sequence}\nevent: run_event\ndata: {data}\n\n"


async def event_stream(
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    after_sequence: int,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    cursor = after_sequence
    idle_seconds = 0.0
    while True:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(Event)
                        .where(Event.run_id == run_id, Event.sequence > cursor)
                        .order_by(Event.sequence)
                        .limit(200)
                    )
                )
                .scalars()
                .all()
            )
        if rows:
            idle_seconds = 0.0
            for event in rows:
                cursor = event.sequence
                yield sse_frame(event)
        else:
            idle_seconds += poll_interval
            if idle_seconds >= KEEPALIVE_SECONDS:
                idle_seconds = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(poll_interval)


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
    after_sequence: int | None = None,
    before_sequence: int | None = None,
    category: str | None = None,
    severity: str | None = None,
    limit: int = DEFAULT_LIMIT,
):
    run = await owned_run(session, principal_id, run_id)
    if run is None:
        return problem_response(
            request, 404, title="Not Found", detail="Run not found."
        )

    query = select(Event).where(Event.run_id == run_id)
    if after_sequence is not None:
        query = query.where(Event.sequence > after_sequence)
    if before_sequence is not None:
        query = query.where(Event.sequence < before_sequence)
    if category is not None:
        query = query.where(Event.category == category)
    if severity is not None:
        try:
            severity_value = EventSeverity(severity)
        except ValueError:
            return problem_response(
                request,
                400,
                title="Bad Request",
                detail="Unknown severity.",
                code="INVALID_SEVERITY",
            )
        query = query.where(Event.severity == severity_value)

    events = (
        (
            await session.execute(
                query.order_by(Event.sequence).limit(max(1, min(limit, MAX_LIMIT)))
            )
        )
        .scalars()
        .all()
    )
    return {"items": [event_response(event) for event in events], "next_cursor": None}


@router.get("/runs/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal_id: Annotated[str, Depends(get_principal_id)],
    after_sequence: int | None = None,
):
    run = await owned_run(session, principal_id, run_id)
    if run is None:
        return problem_response(
            request, 404, title="Not Found", detail="Run not found."
        )

    header_cursor = request.headers.get("Last-Event-ID")
    if after_sequence is not None:
        cursor = after_sequence
    elif header_cursor is not None and header_cursor.isdigit():
        cursor = int(header_cursor)
    else:
        cursor = 0

    earliest = (
        await session.execute(
            select(func.min(Event.sequence)).where(Event.run_id == run_id)
        )
    ).scalar()
    if earliest is not None and cursor < earliest - 1:
        return problem_response(
            request,
            410,
            title="Gone",
            detail="The requested event cursor is no longer available.",
            code="EVENT_CURSOR_EXPIRED",
            extra={
                "earliest_available_sequence": earliest,
                "last_event_sequence": run.last_event_sequence,
            },
        )

    factory = request.app.state.session_factory
    return StreamingResponse(
        event_stream(factory, run_id, cursor),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
