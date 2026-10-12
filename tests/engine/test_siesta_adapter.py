import asyncio
import json
import subprocess

import pytest

from engine.base import (
    EngineEvent,
    EngineInteractionResponse,
    EngineOutcome,
    EngineRunRequest,
)
from engine.siesta import SiestaAdapter, SiestaAdapterError

FAKE_ENGINE = r"""
import json, os, sys
from pathlib import Path

factory = Path(os.environ["SIESTA_FACTORY"])
capture = Path(os.environ["FAKE_CAPTURE"])
response_file = os.environ.get("SIESTA_INTERACTION_RESPONSE_FILE")
payload = {
    "argv": sys.argv[1:],
    "channel": os.environ.get("SIESTA_HUMAN_CHANNEL"),
    "response": json.loads(Path(response_file).read_text()) if response_file else None,
}
project = factory / "projects" / "build-it"
project.mkdir(parents=True, exist_ok=True)
(project / ".pipeline-checkpoint").write_text("phase-0\n")
state = {
    "format_version": 1,
    "interaction_id": "int-engine-1",
    "kind": "intent_confirmation",
    "turn": 2,
    "question": "A menu-bar pomodoro timer.",
    "recommendation": None,
    "final": True,
    "transcript_sha256": "sha256:x",
    "created_at": "2026-10-12T00:00:00Z",
    "consumed": False,
    "raw": "INTENT_FINALIZED: A menu-bar pomodoro timer.",
}
(project / ".pipeline-interaction.json").write_text(json.dumps(state))
capture.write_text(json.dumps(payload))
"""


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


def test_launch_clears_tracked_stop_marker_and_commits(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    subprocess.run(["git", "init", "-b", "main"], cwd=workspace, check=True, env=env)
    (workspace / "stop.md").write_text("old stop")
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, env=env)
    subprocess.run(["git", "commit", "-m", "sweep"], cwd=workspace, check=True, env=env)
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build it",
    )

    adapter._prepare_launch()

    assert not (workspace / "stop.md").exists()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == ""


def test_launch_clears_untracked_stop_marker_without_commit(tmp_path):
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


def make_fake_engine_source(tmp_path):
    source = tmp_path / "source"
    (source / "pipeline").mkdir(parents=True)
    (source / "pipeline" / "__init__.py").write_text("")
    (source / "pipeline" / "__main__.py").write_text(FAKE_ENGINE)
    return source


def test_run_surfaces_pending_interaction_and_delivers_response(tmp_path):
    source = make_fake_engine_source(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    capture = tmp_path / "capture.json"
    adapter = SiestaAdapter(
        source_root=source,
        runtime_path=runtime,
        workspace_path=workspace,
        objective="build it",
        poll_interval=0.05,
        extra_env={"FAKE_CAPTURE": str(capture)},
    )
    request = EngineRunRequest(
        project_id="project-1",
        run_id="run-1",
        attempt_id="attempt-1",
        response=EngineInteractionResponse(
            interaction_id="int-engine-1",
            kind="intent_confirmation",
            accept=True,
        ),
    )

    result = asyncio.run(adapter.run(request, RecordingHooks()))

    assert result.outcome is EngineOutcome.WAITING_FOR_HUMAN
    assert result.failure_summary is None
    assert result.interaction is not None
    assert result.interaction.native_id == "int-engine-1"
    assert result.interaction.final is True
    payload = json.loads(capture.read_text())
    assert payload["argv"] == ["build it"]  # Kallula mode: no --auto
    assert payload["channel"] == "external"
    assert payload["response"]["accept"] is True
    assert payload["response"]["interaction_id"] == "int-engine-1"


def test_run_without_response_clears_a_stale_response_file(tmp_path):
    source = make_fake_engine_source(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (runtime / "interaction-response.json").write_text("{}")
    capture = tmp_path / "capture.json"
    adapter = SiestaAdapter(
        source_root=source,
        runtime_path=runtime,
        workspace_path=workspace,
        objective="build it",
        poll_interval=0.05,
        extra_env={"FAKE_CAPTURE": str(capture)},
    )
    request = EngineRunRequest(project_id="p", run_id="r", attempt_id="a")

    asyncio.run(adapter.run(request, RecordingHooks()))

    payload = json.loads(capture.read_text())
    assert payload["response"] is None
    assert not (runtime / "interaction-response.json").exists()


def test_inspect_result_reports_waiting_interaction(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".pipeline-interaction.json").write_text(
        json.dumps(
            {
                "interaction_id": "int-1",
                "kind": "requirements_question",
                "question": "Which UI?",
                "recommendation": "menu bar",
                "consumed": False,
            }
        )
    )
    adapter = SiestaAdapter(
        source_root=tmp_path / "source",
        runtime_path=tmp_path / "runtime",
        workspace_path=workspace,
        objective="build it",
    )

    result = adapter.inspect_result()

    assert result.outcome is EngineOutcome.WAITING_FOR_HUMAN
    assert result.interaction.native_id == "int-1"
    assert result.interaction.question == "Which UI?"
