from enum import StrEnum

from engine.base import EngineOutcome, EngineResult


class FakeScenario(StrEnum):
    COMPLETE_IMMEDIATELY = "complete_immediately"
    FAIL_DURING_EXECUTION = "fail_during_execution"


class FakeEngine:
    def __init__(
        self, scenario: FakeScenario | str = FakeScenario.COMPLETE_IMMEDIATELY
    ) -> None:
        self.scenario = FakeScenario(scenario)

    def run(self) -> EngineResult:
        if self.scenario is FakeScenario.FAIL_DURING_EXECUTION:
            return EngineResult(
                outcome=EngineOutcome.FAILED,
                failure_summary="Fake engine failed during execution.",
            )
        return EngineResult(outcome=EngineOutcome.COMPLETED)
