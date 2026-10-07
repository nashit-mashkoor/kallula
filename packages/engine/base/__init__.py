from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EngineOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EngineResult:
    outcome: EngineOutcome
    failure_summary: str | None = None


class Engine(Protocol):
    def run(self) -> EngineResult: ...
