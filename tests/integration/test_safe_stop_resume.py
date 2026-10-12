import asyncio
import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import create_app
from api.settings import Settings
from coordinator.active import ActiveRuns
from coordinator.commands import process_commands
from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.loop import process_queued_runs
from coordinator.settings import CoordinatorSettings
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory
from persistence.models import Run, RunEngineRuntime

VENDOR_FACTORY = Path(__file__).resolve().parents[2] / "vendor/siesta/factory"

STUB_PI = r"""#!/bin/bash
sleep 2
model="" prev=""
for a in "$@"; do [ "$prev" = "--model" ] && model="$a"; prev="$a"; done
case "$model" in
  glm-5.2:cloud)
    case "$*" in
      *"spec-driven-development"*) printf '# Spec\n\nA tiny todo CLI in Python.\n' ;;
      *"planning-and-task-breakdown"*) printf '# Issues\n\n## Issue #1: Add hello\nWrite hello.\n\n## Issue #2: Add bye\nWrite bye.\n' ;;
      *"factory-learner"*) printf 'PROJECT_LEARNING:\n  Project: stub\n  Actions:\n    LEARNING: stub learning — detail\n' ;;
      *"Evaluate if this review meets"*) printf 'APPROVED: meets the definition of done\n' ;;
      *"A worker requests approval"*) printf 'APPROVED: aligned with the intent\n' ;;
      *) printf 'INTENT_FINALIZED: a tiny todo cli\n' ;;
    esac ;;
  gemma4:31b-cloud)
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


async def prepare(database_url: str) -> None:
    engine = create_db_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def register(database_url: str, settings: CoordinatorSettings) -> None:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await register_pinned_installation(session, settings)
            await session.commit()
    finally:
        await engine.dispose()


async def read_state(database_url: str, run_id: str) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            run = (
                await session.execute(select(Run).where(Run.id == run_id))
            ).scalar_one()
            return run.control_state.value
    finally:
        await engine.dispose()


async def read_runtime_id(database_url: str, run_id: str) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            runtime = (
                await session.execute(
                    select(RunEngineRuntime).where(RunEngineRuntime.run_id == run_id)
                )
            ).scalar_one()
            return runtime.id
    finally:
        await engine.dispose()


def test_safe_stop_then_resume_same_run(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'stop-resume.db'}"
    workspace_root = tmp_path / "workspaces"
    asyncio.run(prepare(database_url))
    coordinator_settings = CoordinatorSettings(
        database_url=database_url,
        workspace_root=workspace_root,
        engine_source_root=VENDOR_FACTORY,
        development_mode=True,
        engine_poll_interval_seconds=0.2,
        _env_file=None,
    )
    asyncio.run(register(database_url, coordinator_settings))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "pi"
    stub.write_text(STUB_PI)
    stub.chmod(0o755)
    engine_factory = build_engine_factory(
        coordinator_settings,
        extra_env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )
    assert engine_factory is not None
    settings = Settings(
        database_url=database_url,
        workspace_root=workspace_root,
        log_level="WARNING",
        _env_file=None,
    )
    active = ActiveRuns()

    async def drive_once() -> int:
        engine = create_db_engine(database_url)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                return await process_queued_runs(
                    session,
                    holder_id="dod",
                    engine_factory=engine_factory,
                    active=active,
                )
        finally:
            await engine.dispose()

    with TestClient(create_app(settings)) as client:
        project = client.post(
            "/api/v1/projects",
            json={"display_name": "Fault Flow"},
            headers={"Idempotency-Key": "fault-project"},
        ).json()
        run = client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"objective": "build a tiny todo cli"},
            headers={"Idempotency-Key": "fault-run"},
        ).json()
        run_id = run["id"]

        async def stop_mid_run() -> None:
            drive = asyncio.create_task(drive_once())
            state = ""
            for _ in range(100):
                state = await read_state(database_url, run_id)
                if state == "RUNNING":
                    break
                await asyncio.sleep(0.3)
            assert state == "RUNNING"

            response = await asyncio.to_thread(
                client.post,
                f"/api/v1/runs/{run_id}/commands/stop",
                json={"mode": "SAFE"},
                headers={"Idempotency-Key": "fault-stop"},
            )
            assert response.status_code == 202

            engine = create_db_engine(database_url)
            factory = create_session_factory(engine)
            try:
                async with factory() as session:
                    applied = await process_commands(session, active=active)
                    assert applied == 1
            finally:
                await engine.dispose()
            await asyncio.wait_for(drive, timeout=120)

        asyncio.run(stop_mid_run())

        stopped = client.get(f"/api/v1/runs/{run_id}").json()
        assert stopped["control_state"] == "STOPPED"
        attempts = client.get(f"/api/v1/runs/{run_id}/attempts").json()["items"]
        assert [attempt["ordinal"] for attempt in attempts] == [1]
        assert attempts[0]["terminal_reason"] == "SAFE_STOP"
        runtime_id = asyncio.run(read_runtime_id(database_url, run_id))

        workspace = workspace_root / "projects" / project["id"] / "workspace"
        assert (workspace / "stop.md").is_file()

        response = client.post(
            f"/api/v1/runs/{run_id}/commands/resume",
            json={"reason": "USER_REQUEST"},
            headers={"Idempotency-Key": "fault-resume"},
        )
        assert response.status_code == 202
        resumed = client.get(f"/api/v1/runs/{run_id}").json()
        assert resumed["control_state"] == "QUEUED"

        assert asyncio.run(drive_once()) == 1

        final = client.get(f"/api/v1/runs/{run_id}").json()
        assert final["control_state"] == "COMPLETED"
        attempts = client.get(f"/api/v1/runs/{run_id}/attempts").json()["items"]
        assert [attempt["ordinal"] for attempt in attempts] == [1, 2]
        assert attempts[1]["state"] == "EXITED"

        assert asyncio.run(read_runtime_id(database_url, run_id)) == runtime_id
        assert not (workspace / "stop.md").exists()
        assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"

        with TestClient(create_app(settings)) as fresh:
            fresh_run = fresh.get(f"/api/v1/runs/{run_id}").json()
            assert fresh_run["control_state"] == "COMPLETED"
            assert (
                fresh.get(f"/api/v1/runs/{run_id}/attempts").json()["items"][-1][
                    "ordinal"
                ]
                == 2
            )
