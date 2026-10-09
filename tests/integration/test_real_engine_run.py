import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from coordinator.engines import build_engine_factory
from coordinator.loop import process_queued_runs
from coordinator.settings import CoordinatorSettings
from domain.states import (
    EngineRuntimeState,
    EventSource,
    RunControlState,
    WorkItemState,
    WorkspaceStatus,
)
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import (
    Artifact,
    Event,
    Principal,
    Project,
    Run,
    RunEngineRuntime,
    WorkItem,
    Workspace,
)
from runtime.base.workspace import WorkspaceManager

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"

STUB_PI = r"""#!/bin/bash
d="$(dirname "$0")"
env > "$d/pi_env.txt"
scenario="$(cat "$d/scenario" 2>/dev/null || echo pass)"
model="" prev=""
for a in "$@"; do [ "$prev" = "--model" ] && model="$a"; prev="$a"; done
case "$model" in
  glm-5.2:cloud)
    case "$*" in
      *"spec-driven-development"*) printf '# Spec\n\nA tiny todo CLI in Python.\n' ;;
      *"planning-and-task-breakdown"*) printf '# Issues\n\n## Issue #1: Add hello\nWrite hello.\n\n## Issue #2: Add bye\nWrite bye.\n' ;;
      *"factory-learner"*) printf 'PROJECT_LEARNING:\n  Project: run\n  Actions:\n    LEARNING: stub learning — detail\n' ;;
      *"Evaluate if this review meets"*) printf 'APPROVED: meets the definition of done\n' ;;
      *"A worker requests approval"*) printf 'APPROVED: aligned with the intent\n' ;;
      *) printf 'RESOLUTION: use the standard library\nAPPROACH: simplest path\n' ;;
    esac ;;
  gemma4:31b-cloud)
    case "$*" in
      *"QA engineer"*)
        if [ "$scenario" = "verify_fail" ]; then
          printf 'VERIFY_FAILED: the entry point does not run\n'
        else
          printf 'VERIFY_PASSED: static verification complete\n'
        fi ;;
      *"code-reviewer"*) printf 'REVIEW_PASSED: no issues found\n' ;;
      *) printf 'def greeting():\n    return "hello"\n' > todo.py
         printf 'from todo import greeting\n\ndef test_greeting():\n    assert greeting() == "hello"\n' > test_todo.py
         printf 'ISSUE_OK: implemented the change with tests\n' ;;
    esac ;;
  *) printf 'unexpected model %s\n' "$model" >&2; exit 3 ;;
esac
"""


async def prepare(database_url: str):
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


def make_stub(tmp_path: Path, scenario: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "pi"
    stub.write_text(STUB_PI)
    stub.chmod(0o755)
    (bin_dir / "scenario").write_text(scenario)
    return bin_dir


def execute_run(database_url: str, tmp_path: Path, scenario: str) -> dict:
    async def scenario_fn():
        engine = await prepare(database_url)
        factory = create_session_factory(engine)
        workspace_root = tmp_path / "workspaces"
        try:
            async with factory() as session:
                principal = Principal(
                    auth_provider="development",
                    auth_subject="dev",
                    display_name="Dev",
                )
                session.add(principal)
                await session.flush()
                project = Project(owner_id=principal.id, display_name="Project")
                session.add(project)
                await session.flush()
                workspace_key = f"projects/{project.id}/workspace"
                WorkspaceManager(workspace_root).allocate(workspace_key)
                workspace = Workspace(
                    project_id=project.id,
                    storage_driver="local",
                    storage_key=workspace_key,
                    status=WorkspaceStatus.READY,
                )
                session.add(workspace)
                run = Run(
                    project_id=project.id,
                    ordinal=1,
                    objective="build a tiny todo cli",
                )
                session.add(run)
                await session.commit()
                run_id = run.id
                project_id = project.id
                workspace_path = workspace_root / workspace_key

            bin_dir = make_stub(tmp_path, scenario)
            settings = CoordinatorSettings(
                database_url=database_url,
                workspace_root=workspace_root,
                engine_source_root=VENDOR_FACTORY,
                development_mode=True,
                engine_poll_interval_seconds=0.2,
                _env_file=None,
            )
            engine_factory = build_engine_factory(
                settings,
                extra_env={
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                },
            )
            assert engine_factory is not None

            async with factory() as session:
                processed = await process_queued_runs(
                    session, holder_id="test", engine_factory=engine_factory
                )
                assert processed == 1

            async with factory() as session:
                run = (
                    await session.execute(select(Run).where(Run.id == run_id))
                ).scalar_one()
                work_items = (
                    (await session.execute(select(WorkItem).order_by(WorkItem.ordinal)))
                    .scalars()
                    .all()
                )
                artifacts = (await session.execute(select(Artifact))).scalars().all()
                events = (
                    (
                        await session.execute(
                            select(Event)
                            .where(Event.source == EventSource.ENGINE_ADAPTER)
                            .order_by(Event.sequence)
                        )
                    )
                    .scalars()
                    .all()
                )
                runtime = (await session.execute(select(RunEngineRuntime))).scalar_one()
                return {
                    "project_id": project_id,
                    "run": run,
                    "work_items": list(work_items),
                    "artifact_classes": {
                        artifact.artifact_class.value for artifact in artifacts
                    },
                    "engine_event_types": [event.event_type for event in events],
                    "runtime_state": runtime.state,
                    "runtime_storage_key": runtime.storage_key,
                    "workspace_path": workspace_path,
                }
        finally:
            await engine.dispose()

    return asyncio.run(scenario_fn())


def test_real_engine_run_completes_with_normalized_progress(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'complete.db'}"

    result = execute_run(database_url, tmp_path, "pass")
    run = result["run"]

    assert run.control_state is RunControlState.COMPLETED
    assert run.failure_code is None
    assert run.current_stage_category == "LEARNING"
    assert [item.engine_key for item in result["work_items"]] == [
        "issue:1",
        "issue:2",
    ]
    assert [item.title for item in result["work_items"]] == ["Add hello", "Add bye"]
    assert [item.state for item in result["work_items"]] == [
        WorkItemState.COMPLETED,
        WorkItemState.COMPLETED,
    ]
    assert {
        "SPECIFICATION",
        "PLAN",
        "TEST_EVIDENCE",
        "VERIFICATION_EVIDENCE",
    } <= result["artifact_classes"]
    assert "WORK_ITEM_COMPLETED" in result["engine_event_types"]
    assert "ARTIFACT_DISCOVERED" in result["engine_event_types"]
    assert result["runtime_state"] is EngineRuntimeState.READY
    assert result["runtime_storage_key"].endswith("engine-runtime")
    workspace = result["workspace_path"]
    assert (workspace / "spec.md").is_file()
    assert (workspace / "issues.md").is_file()
    assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"


def test_real_engine_run_fails_without_verified_completion(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'fail.db'}"

    result = execute_run(database_url, tmp_path, "verify_fail")
    run = result["run"]

    assert run.control_state is RunControlState.FAILED
    assert run.failure_class == "ENGINE_FAILURE"
    assert run.failure_code == "ENGINE_UNVERIFIED"
    assert run.failure_summary
    assert "VERIFICATION_COMPLETED" in result["engine_event_types"]
    assert "WORK_ITEM_COMPLETED" in result["engine_event_types"]
    assert {item.state for item in result["work_items"]} == {WorkItemState.COMPLETED}
