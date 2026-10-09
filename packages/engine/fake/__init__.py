from enum import StrEnum

from engine.base import (
    EngineCapabilities,
    EngineDescriptor,
    EngineEvent,
    EngineHooks,
    EngineIdentity,
    EngineOutcome,
    EngineResult,
    EngineRunRequest,
    EngineStage,
    StageCategory,
)


class FakeScenario(StrEnum):
    COMPLETE_IMMEDIATELY = "complete_immediately"
    FAIL_DURING_EXECUTION = "fail_during_execution"
    EMIT_WORK_ITEMS = "emit_work_items"


FAKE_IDENTITY = EngineIdentity(family="FAKE", revision="1", adapter_version="1")
FAKE_CAPABILITIES = EngineCapabilities(autonomous_defaults=True, work_items=True)


class FakeEngine:
    def __init__(
        self, scenario: FakeScenario | str = FakeScenario.COMPLETE_IMMEDIATELY
    ) -> None:
        self.scenario = FakeScenario(scenario)

    def describe(self) -> EngineDescriptor:
        return EngineDescriptor(identity=FAKE_IDENTITY, capabilities=FAKE_CAPABILITIES)

    async def run(self, request: EngineRunRequest, hooks: EngineHooks) -> EngineResult:
        if self.scenario is FakeScenario.FAIL_DURING_EXECUTION:
            return EngineResult(
                outcome=EngineOutcome.FAILED,
                failure_summary="Fake engine failed during execution.",
            )
        if self.scenario is FakeScenario.EMIT_WORK_ITEMS:
            await self._emit_work_items(hooks)
        return EngineResult(outcome=EngineOutcome.COMPLETED_VERIFIED)

    async def _emit_work_items(self, hooks: EngineHooks) -> None:
        stage = EngineStage(
            category=StageCategory.EXECUTION, display_label="Execution", order=4
        )
        events = [
            EngineEvent(
                event_type="STAGE_STARTED",
                category="STAGE",
                summary="Stage Execution started.",
                source_event_sequence=1,
                stage=stage,
            ),
            EngineEvent(
                event_type="WORK_ITEM_STARTED",
                category="WORK_ITEM",
                summary="Work item 1 started.",
                source_event_sequence=2,
                stage=stage,
                work_item_native_id="1",
            ),
            EngineEvent(
                event_type="WORK_ITEM_COMPLETED",
                category="WORK_ITEM",
                summary="Work item 1 completed.",
                source_event_sequence=3,
                stage=stage,
                work_item_native_id="1",
            ),
            EngineEvent(
                event_type="STAGE_COMPLETED",
                category="STAGE",
                summary="Stage Execution completed.",
                source_event_sequence=4,
                stage=stage,
            ),
        ]
        for event in events:
            await hooks.on_event(event)
