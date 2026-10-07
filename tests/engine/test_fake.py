from engine.base import EngineOutcome
from engine.fake import FakeEngine, FakeScenario


def test_complete_immediately():
    result = FakeEngine(FakeScenario.COMPLETE_IMMEDIATELY).run()

    assert result.outcome is EngineOutcome.COMPLETED
    assert result.failure_summary is None


def test_fail_during_execution():
    result = FakeEngine("fail_during_execution").run()

    assert result.outcome is EngineOutcome.FAILED
    assert result.failure_summary
