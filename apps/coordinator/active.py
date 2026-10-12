import asyncio
from dataclasses import dataclass, field


@dataclass
class ActiveRun:
    signal: asyncio.Event = field(default_factory=asyncio.Event)
    project_id: str | None = None
    holder_id: str | None = None
    lease_epoch: int | None = None


class ActiveRuns:
    def __init__(self) -> None:
        self._runs: dict[str, ActiveRun] = {}

    def register(self, run_id: str) -> ActiveRun:
        entry = ActiveRun()
        self._runs[run_id] = entry
        return entry

    def unregister(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    def signal(self, run_id: str) -> bool:
        entry = self._runs.get(run_id)
        if entry is None:
            return False
        entry.signal.set()
        return True

    def is_active(self, run_id: str) -> bool:
        return run_id in self._runs

    def items(self) -> list[tuple[str, ActiveRun]]:
        return list(self._runs.items())
