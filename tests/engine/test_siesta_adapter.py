import asyncio

import pytest

from engine.base import EngineEvent, EngineRunRequest
from engine.siesta import SiestaAdapter, SiestaAdapterError


class RecordingHooks:
    def __init__(self) -> None:
        self.events: list[EngineEvent] = []

    async def on_event(self, event: EngineEvent) -> None:
        self.events.append(event)


def test_adapter_rejects_conflicting_objective(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".pipeline-idea").write_text("NASHIT\n")
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build a different thing",
    )
    request = EngineRunRequest(project_id="p", run_id="r", attempt_id="a")

    with pytest.raises(SiestaAdapterError) as excinfo:
        asyncio.run(adapter.run(request, RecordingHooks()))

    assert excinfo.value.code == "SIESTA_OBJECTIVE_CONFLICT"
    assert not (tmp_path / "runtime" / "projects").exists()
