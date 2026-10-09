from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import EventSeverity, EventSource
from persistence.models import Event, Run


async def append_event(
    session: AsyncSession,
    run: Run,
    *,
    event_type: str,
    category: str,
    summary: str,
    source: EventSource = EventSource.RUN_COORDINATOR,
    severity: EventSeverity = EventSeverity.INFO,
    attempt_id: str | None = None,
    source_event_sequence: int | None = None,
    payload: dict | None = None,
    payload_version: int = 1,
    stage_category: str | None = None,
    stage_native_id: str | None = None,
    stage_label: str | None = None,
    stage_order: int | None = None,
    work_item_id: str | None = None,
    artifact_ids: list[str] | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    sequence = run.last_event_sequence + 1
    event = Event(
        run_id=run.id,
        sequence=sequence,
        attempt_id=attempt_id,
        source=source,
        source_event_sequence=source_event_sequence,
        event_type=event_type,
        category=category,
        severity=severity,
        stage_category=stage_category,
        stage_native_id=stage_native_id,
        stage_label=stage_label,
        stage_order=stage_order,
        work_item_id=work_item_id,
        summary=summary,
        payload_version=payload_version,
        payload_json=payload or {},
        artifact_ids_json=artifact_ids or [],
        occurred_at=occurred_at or datetime.now(UTC),
    )
    session.add(event)
    run.last_event_sequence = sequence
    await session.flush()
    return event
