from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.states import EventSource
from engine.base import EngineEvent
from persistence import artifacts, work_items
from persistence.events import append_event
from persistence.models import Event, Run, WorkItem


class RunEventSink:
    def __init__(self, session: AsyncSession, run: Run, attempt_id: str) -> None:
        self._session = session
        self._run = run
        self._attempt_id = attempt_id

    async def on_event(self, event: EngineEvent) -> None:
        if await self._already_ingested(event):
            return
        work_item = await self._work_item_for(event)
        artifact_ids = await self._store_artifacts(event)
        stage = event.stage
        await append_event(
            self._session,
            self._run,
            event_type=event.event_type,
            category=event.category,
            summary=event.summary,
            source=EventSource.ENGINE_ADAPTER,
            severity=event.severity,
            attempt_id=self._attempt_id,
            source_event_sequence=event.source_event_sequence,
            payload=dict(event.payload) if event.payload else None,
            stage_category=stage.category.value if stage else None,
            stage_native_id=stage.native_id if stage else None,
            stage_label=stage.display_label if stage else None,
            stage_order=stage.order if stage else None,
            work_item_id=work_item.id if work_item else None,
            artifact_ids=artifact_ids or None,
            occurred_at=event.occurred_at,
        )
        self._apply_run_progress(event, work_item)

    async def _already_ingested(self, event: EngineEvent) -> bool:
        if event.source_event_sequence is None:
            return False
        existing = (
            await self._session.execute(
                select(Event.id).where(
                    Event.attempt_id == self._attempt_id,
                    Event.source_event_sequence == event.source_event_sequence,
                )
            )
        ).scalar_one_or_none()
        return existing is not None

    async def _work_item_for(self, event: EngineEvent) -> WorkItem | None:
        native_id = event.work_item_native_id
        if native_id is None:
            return None
        title = event.payload.get("title") if event.payload else None
        blocker = event.payload.get("blocker") if event.payload else None
        if event.event_type == "WORK_ITEM_DISCOVERED":
            return await work_items.record_discovered(
                self._session, self._run, native_id, title
            )
        if event.event_type == "WORK_ITEM_STARTED":
            return await work_items.record_started(
                self._session, self._run, native_id, title
            )
        if event.event_type == "WORK_ITEM_COMPLETED":
            return await work_items.record_completed(
                self._session, self._run, native_id, title
            )
        if event.event_type == "WORK_ITEM_BLOCKED":
            return await work_items.record_blocked(
                self._session, self._run, native_id, title, blocker
            )
        if event.event_type == "WORK_ITEM_SKIPPED":
            return await work_items.record_skipped(
                self._session, self._run, native_id, title, blocker
            )
        return None

    async def _store_artifacts(self, event: EngineEvent) -> list[str]:
        if event.event_type != "ARTIFACT_DISCOVERED":
            return []
        artifact = await artifacts.store_from_event(
            self._session, self._run, self._attempt_id, dict(event.payload)
        )
        return [artifact.id]

    def _apply_run_progress(
        self, event: EngineEvent, work_item: WorkItem | None
    ) -> None:
        if event.stage is not None and event.event_type in (
            "STAGE_STARTED",
            "STAGE_COMPLETED",
        ):
            self._run.current_stage_category = event.stage.category.value
            self._run.current_stage_native_id = event.stage.native_id
            self._run.current_stage_label = event.stage.display_label
            self._run.current_stage_order = event.stage.order
        if work_item is None:
            return
        if event.event_type == "WORK_ITEM_STARTED":
            self._run.active_work_item_id = work_item.id
        elif (
            event.event_type
            in ("WORK_ITEM_COMPLETED", "WORK_ITEM_BLOCKED", "WORK_ITEM_SKIPPED")
            and self._run.active_work_item_id == work_item.id
        ):
            self._run.active_work_item_id = None
