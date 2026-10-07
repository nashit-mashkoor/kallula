import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import get_principal_id
from persistence.models import Event, Run

router = APIRouter(tags=["stream"])

POLL_INTERVAL_SECONDS = 0.5
KEEPALIVE_SECONDS = 15.0


def _parse_cursor(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def invalidation_stream(
    factory: async_sessionmaker[AsyncSession],
    cursor: datetime | None = None,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    last = cursor
    idle_seconds = 0.0
    while True:
        async with factory() as session:
            query = (
                select(Event, Run)
                .join(Run, Event.run_id == Run.id)
                .order_by(Event.recorded_at, Event.sequence)
            )
            if last is not None:
                query = query.where(Event.recorded_at > last)
            rows = (await session.execute(query.limit(200))).all()
        if rows:
            idle_seconds = 0.0
            for event, run in rows:
                last = event.recorded_at
                data = {
                    "resource_type": "RUN",
                    "resource_id": run.id,
                    "project_id": run.project_id,
                    "version": run.version,
                    "reason": "STATE_CHANGED",
                }
                yield (
                    f"id: {last.isoformat()}\n"
                    "event: resource_changed\n"
                    f"data: {json.dumps(data)}\n\n"
                )
        else:
            idle_seconds += poll_interval
            if idle_seconds >= KEEPALIVE_SECONDS:
                idle_seconds = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(poll_interval)


@router.get("/stream")
async def account_stream(
    request: Request,
    principal_id: Annotated[str, Depends(get_principal_id)],
):
    cursor = _parse_cursor(request.headers.get("Last-Event-ID"))
    factory = request.app.state.session_factory
    return StreamingResponse(
        invalidation_stream(factory, cursor),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
