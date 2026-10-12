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


def test_request_safe_stop_writes_marker_idempotently(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build it",
    )

    adapter.request_safe_stop()
    marker = workspace / "stop.md"
    assert marker.is_file()
    content = marker.read_text()

    adapter.request_safe_stop()

    assert marker.read_text() == content


def test_launch_clears_stale_stop_marker(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "stop.md").write_text("old stop")
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build it",
    )

    adapter._prepare_launch()

    assert not (workspace / "stop.md").exists()
    assert (tmp_path / "runtime" / "projects" / "build-it").is_symlink()


def test_launch_rejects_malformed_native_state(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "kb").mkdir()
    (workspace / "kb" / "graph.json").write_text("{not json")
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build it",
    )

    with pytest.raises(SiestaAdapterError) as excinfo:
        adapter._prepare_launch()

    assert excinfo.value.code == "SIESTA_NATIVE_STATE_INVALID"
