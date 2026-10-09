import asyncio

from engine.base import EngineEvent, EngineOutcome, EngineRunRequest, StageCategory
from engine.fake import FakeEngine, FakeScenario

REQUEST = EngineRunRequest(project_id="project", run_id="run", attempt_id="attempt")


class RecordingHooks:
    def __init__(self) -> None:
        self.events: list[EngineEvent] = []

    async def on_event(self, event: EngineEvent) -> None:
        self.events.append(event)


def run_engine(scenario: FakeScenario | str, hooks: RecordingHooks):
    return asyncio.run(FakeEngine(scenario).run(REQUEST, hooks))


def test_complete_immediately():
    hooks = RecordingHooks()

    result = run_engine(FakeScenario.COMPLETE_IMMEDIATELY, hooks)

    assert result.outcome is EngineOutcome.COMPLETED_VERIFIED
    assert result.failure_summary is None
    assert hooks.events == []


def test_fail_during_execution():
    hooks = RecordingHooks()

    result = run_engine(FakeScenario.FAIL_DURING_EXECUTION, hooks)

    assert result.outcome is EngineOutcome.FAILED
    assert result.failure_summary


def test_emit_work_items_emits_structured_events():
    hooks = RecordingHooks()

    result = run_engine(FakeScenario.EMIT_WORK_ITEMS, hooks)

    assert result.outcome is EngineOutcome.COMPLETED_VERIFIED
    assert [event.event_type for event in hooks.events] == [
        "STAGE_STARTED",
        "WORK_ITEM_DISCOVERED",
        "WORK_ITEM_DISCOVERED",
        "WORK_ITEM_STARTED",
        "WORK_ITEM_COMPLETED",
        "WORK_ITEM_STARTED",
        "WORK_ITEM_COMPLETED",
        "STAGE_COMPLETED",
    ]
    assert [event.source_event_sequence for event in hooks.events] == list(range(1, 9))
    assert all(event.stage is not None for event in hooks.events)
    assert all(
        event.stage.category is StageCategory.EXECUTION for event in hooks.events
    )
    assert [event.work_item_native_id for event in hooks.events] == [
        None,
        "1",
        "2",
        "1",
        "1",
        "2",
        "2",
        None,
    ]
    discovered = [
        event.payload["title"]
        for event in hooks.events
        if event.event_type == "WORK_ITEM_DISCOVERED"
    ]
    assert discovered == ["Add hello", "Add bye"]


def test_describe_reports_identity_and_capabilities():
    descriptor = FakeEngine().describe()

    assert descriptor.identity.family == "FAKE"
    assert descriptor.identity.revision
    assert descriptor.capabilities.autonomous_defaults is True
    assert descriptor.capabilities.work_items is True
    assert descriptor.capabilities.human_requirements is False
