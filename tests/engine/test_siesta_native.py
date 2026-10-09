import json
from pathlib import Path

import pytest

from engine.base import EngineOutcome
from engine.siesta import (
    SiestaAdapterError,
    classify_outcome,
    discover_artifacts,
    inspect_workspace,
    project_slug,
)
from engine.siesta.native import NativeState


def make_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    workspace.mkdir()
    return workspace


def test_project_slug_follows_pinned_revision_rules():
    assert project_slug("Build a tiny TODO CLI!") == "build-a-tiny-todo-cli"
    truncated = project_slug("alpha beta gamma delta epsilon zeta eta theta iota")
    assert len(truncated) <= 40
    assert truncated.startswith("alpha-beta-gamma-delta-epsilon")


def test_project_slug_rejects_unusable_objective():
    with pytest.raises(SiestaAdapterError) as excinfo:
        project_slug("!!!")

    assert excinfo.value.code == "SIESTA_OBJECTIVE_INVALID"


def test_inspect_workspace_reads_native_evidence(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / ".pipeline-checkpoint").write_text("phase-3\n")
    (workspace / "issues.md").write_text(
        "## Issue #1: A\nbody\n\n## Issue #2: B\nbody\n"
    )
    (workspace / "pre_issue_1.json").write_text("{}")
    (workspace / "verify_verdict.txt").write_text("VERIFY_FAILED\n")
    kb = workspace / "kb"
    kb.mkdir()
    (kb / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"type": "decision", "summary": "Issue #1 completed"},
                    {"type": "blocker", "summary": "Issue #2 blocked: tests red"},
                    {"type": "blocker", "summary": "Pipeline failed"},
                ]
            }
        )
    )

    state = inspect_workspace(workspace)

    assert state.checkpoint == "phase-3"
    assert state.issues == (1, 2)
    assert state.started_issues == (1,)
    assert state.completed_issues == (1,)
    assert state.blocked_issues == (2,)
    assert state.verdict == "VERIFY_FAILED"
    assert state.failed is True


def test_inspect_workspace_reports_malformed_ledger(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "kb").mkdir()
    (workspace / "kb" / "graph.json").write_text("{not json")

    with pytest.raises(SiestaAdapterError) as excinfo:
        inspect_workspace(workspace)

    assert excinfo.value.code == "SIESTA_NATIVE_STATE_INVALID"


def test_inspect_workspace_without_project_state(tmp_path):
    state = inspect_workspace(make_workspace(tmp_path))

    assert state == NativeState(None, (), (), (), (), None, False)


def test_classify_outcome_verified_completion():
    state = NativeState("complete", (1,), (1,), (1,), (), "VERIFY_PASSED", False)

    outcome, summary = classify_outcome(state, 0)

    assert outcome is EngineOutcome.COMPLETED_VERIFIED
    assert summary is None


def test_classify_outcome_blocked_work_is_not_verified():
    state = NativeState("phase-3", (1, 2), (1, 2), (1,), (2,), "VERIFY_FAILED", False)

    outcome, summary = classify_outcome(state, 1)

    assert outcome is EngineOutcome.TERMINAL_UNVERIFIED_OR_INCOMPLETE
    assert summary is not None
    assert "#2" in summary


def test_classify_outcome_pipeline_failure():
    state = NativeState("phase-0", (), (), (), (), None, True)

    outcome, summary = classify_outcome(state, 1)

    assert outcome is EngineOutcome.FAILED
    assert summary


def test_classify_outcome_crash_without_native_state():
    state = NativeState(None, (), (), (), (), None, False)

    outcome, summary = classify_outcome(state, 2)

    assert outcome is EngineOutcome.FAILED
    assert summary is not None
    assert "status 2" in summary


def test_discover_artifacts_maps_documented_patterns(tmp_path):
    workspace = make_workspace(tmp_path)
    (workspace / "spec.md").write_text("spec")
    (workspace / "issues.md").write_text("issues")
    (workspace / "issue_1_output.txt").write_text("output")
    (workspace / "kb").mkdir()
    (workspace / "kb" / "graph.json").write_text("{}")

    artifacts = discover_artifacts(workspace)

    classes = {artifact.normalized_class for artifact in artifacts}
    assert {
        "specification",
        "implementation_plan",
        "issue_output",
        "project_knowledge",
    } <= classes
    assert all(artifact.path.is_file() for artifact in artifacts)
