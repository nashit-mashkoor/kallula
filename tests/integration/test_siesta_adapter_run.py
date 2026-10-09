import asyncio
import json
import os
from pathlib import Path

from engine.base import EngineEvent, EngineOutcome, EngineRunRequest
from engine.siesta import SiestaAdapter
from runtime.base.engine_runtime import EngineRuntimeManager
from runtime.base.workspace import WorkspaceManager

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"
VENDOR_REVISION = "20b149e0734b09730dfd22803d2695776fcf84b8"

STUB_PI = r"""#!/bin/bash
d="$(dirname "$0")"
env > "$d/pi_env.txt"
model="" prev=""
for a in "$@"; do [ "$prev" = "--model" ] && model="$a"; prev="$a"; done
case "$model" in
  planner-model)
    case "$*" in
      *"spec-driven-development"*) printf '# Spec\n\nA tiny todo CLI in Python.\n' ;;
      *"planning-and-task-breakdown"*) printf '# Issues\n\n## Issue #1: Add hello\nWrite hello.\n\n## Issue #2: Add bye\nWrite bye.\n' ;;
      *) printf 'INTENT_FINALIZED: a tiny todo cli\n' ;;
    esac ;;
  consultant-model)
    case "$*" in
      *"factory-learner"*) printf 'PROJECT_LEARNING:\n  Project: stub\n  Actions:\n    LEARNING: stub learning — detail\n' ;;
      *"Evaluate if this review meets"*) printf 'APPROVED: meets the definition of done\n' ;;
      *"A worker requests approval"*) printf 'APPROVED: aligned with the intent\n' ;;
      *) printf 'RESOLUTION: use the standard library\nAPPROACH: simplest path\n' ;;
    esac ;;
  worker-model)
    case "$*" in
      *"QA engineer"*) printf 'VERIFY_PASSED: static verification complete\n' ;;
      *"code-reviewer"*) printf 'REVIEW_PASSED: no issues found\n' ;;
      *) printf 'def greeting():\n    return "hello"\n' > todo.py
         printf 'from todo import greeting\n\ndef test_greeting():\n    assert greeting() == "hello"\n' > test_todo.py
         printf 'ISSUE_OK: implemented the change with tests\n' ;;
    esac ;;
  *) printf 'unexpected model %s\n' "$model" >&2; exit 3 ;;
esac
"""

MODELS = {
    "planner": {"model": "planner-model", "provider": "ollama"},
    "worker": {"model": "worker-model", "provider": "ollama"},
    "consultant": {"model": "consultant-model", "provider": "ollama"},
}


class RecordingHooks:
    def __init__(self) -> None:
        self.events: list[EngineEvent] = []

    async def on_event(self, event: EngineEvent) -> None:
        self.events.append(event)


def test_adapter_launches_pinned_revision_with_workspace_injection(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    runtime = EngineRuntimeManager(root).ensure(
        "projects/project-1/runs/run-1/engine-runtime", VENDOR_FACTORY
    )
    (runtime / "config" / "models.json").write_text(json.dumps(MODELS))
    workspace = WorkspaceManager(root).allocate("projects/project-1/workspace")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "pi"
    stub.write_text(STUB_PI)
    stub.chmod(0o755)
    monkeypatch.setenv("KALLULA_TEST_SECRET", "sentinel")

    adapter = SiestaAdapter(
        source_root=VENDOR_FACTORY,
        runtime_path=runtime,
        workspace_path=workspace,
        objective="build a tiny todo cli",
        poll_interval=0.2,
        extra_env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )
    assert adapter.describe().identity.revision == VENDOR_REVISION

    hooks = RecordingHooks()
    request = EngineRunRequest(
        project_id="project-1", run_id="run-1", attempt_id="attempt-1"
    )

    result = asyncio.run(adapter.run(request, hooks))

    assert result.outcome is EngineOutcome.COMPLETED_VERIFIED
    assert result.failure_summary is None
    assert (workspace / "spec.md").is_file()
    assert (workspace / "issues.md").is_file()
    assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"
    assert (workspace / "kb" / "graph.json").is_file()
    assert (workspace / "test_todo.py").is_file()
    assert (runtime / "kb" / "global-graph.json").is_file()
    symlink = runtime / "projects" / "build-a-tiny-todo-cli"
    assert symlink.is_symlink()
    assert symlink.resolve() == workspace.resolve()

    pi_env = (bin_dir / "pi_env.txt").read_text()
    assert "KALLULA_TEST_SECRET" not in pi_env
    assert f"SIESTA_FACTORY={runtime}" in pi_env

    event_types = [event.event_type for event in hooks.events]
    assert event_types[0] == "STAGE_STARTED"
    assert "STAGE_COMPLETED" in event_types
    assert "WORK_ITEM_DISCOVERED" in event_types
    assert "WORK_ITEM_STARTED" in event_types
    assert "WORK_ITEM_COMPLETED" in event_types
    assert "VERIFICATION_COMPLETED" in event_types
    assert [event.source_event_sequence for event in hooks.events] == list(
        range(1, len(event_types) + 1)
    )
    completed = {
        event.work_item_native_id
        for event in hooks.events
        if event.event_type == "WORK_ITEM_COMPLETED"
    }
    assert completed == {"1", "2"}
    verification = next(
        event for event in hooks.events if event.event_type == "VERIFICATION_COMPLETED"
    )
    assert verification.payload == {"verdict": "VERIFY_PASSED"}
