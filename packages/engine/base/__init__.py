from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from domain.states import EventSeverity


class StageCategory(StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    SPECIFICATION = "SPECIFICATION"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    REVIEW = "REVIEW"
    VERIFICATION = "VERIFICATION"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"
    OTHER = "OTHER"


class EngineOutcome(StrEnum):
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    TERMINAL_UNVERIFIED_OR_INCOMPLETE = "TERMINAL_UNVERIFIED_OR_INCOMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EngineStage:
    category: StageCategory
    display_label: str
    order: int
    native_id: str | None = None


@dataclass(frozen=True)
class EngineEvent:
    event_type: str
    category: str
    summary: str
    severity: EventSeverity = EventSeverity.INFO
    source_event_sequence: int | None = None
    stage: EngineStage | None = None
    work_item_native_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class EngineRunRequest:
    project_id: str
    run_id: str
    attempt_id: str


@dataclass(frozen=True)
class EngineResult:
    outcome: EngineOutcome
    failure_summary: str | None = None


@dataclass(frozen=True)
class EngineIdentity:
    family: str
    revision: str
    adapter_version: str
    installation_digest: str | None = None


@dataclass(frozen=True)
class EngineCapabilities:
    human_requirements: bool = False
    autonomous_defaults: bool = False
    safe_stop: bool = False
    resume: bool = False
    work_items: bool = False
    review: bool = False
    verification: bool = False
    learning: bool = False


@dataclass(frozen=True)
class EngineDescriptor:
    identity: EngineIdentity
    capabilities: EngineCapabilities


class EngineError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class EngineHooks(Protocol):
    async def on_event(self, event: EngineEvent) -> None: ...


class Engine(Protocol):
    def describe(self) -> EngineDescriptor: ...

    async def run(
        self, request: EngineRunRequest, hooks: EngineHooks
    ) -> EngineResult: ...
