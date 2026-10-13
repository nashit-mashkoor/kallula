"""M4 Definition of Done: a real engine run suspends on a question, survives
an API restart, continues after a browser answer, and confirms final intent.

The engine, persistence, events and API are real; only the model is the local
stub. The stub conducts one requirements question, finalizes after the answer,
and implements the resulting plan after the confirmation.
"""

import asyncio
import os

from fastapi.testclient import TestClient
from test_real_engine_run import VENDOR_FACTORY

from api.main import create_app
from api.settings import Settings
from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.loop import process_queued_runs
from coordinator.settings import CoordinatorSettings
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory

INTERVIEW_STUB_PI = r"""#!/bin/bash
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
      *"interview-me"*)
        if printf '%s' "$*" | grep -q "A: "; then
          printf 'INTENT_FINALIZED: A tiny todo CLI in Python with a terminal interface.\n'
        else
          printf 'Q: Which UI?\nGUESS: terminal, it is the simplest.\n'
        fi ;;
      *) printf 'RESOLUTION: use the standard library\nAPPROACH: simplest path\n' ;;
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


async def register(database_url: str, settings: CoordinatorSettings) -> str:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            installation = await register_pinned_installation(session, settings)
            await session.commit()
            return installation.id
    finally:
        await engine.dispose()


async def execute(database_url: str, engine_factory) -> int:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            return await process_queued_runs(
                session, holder_id="m4", engine_factory=engine_factory
            )
    finally:
        await engine.dispose()


def make_environment(tmp_path, name: str):
    database_url = f"sqlite+aiosqlite:///{tmp_path / f'{name}.db'}"
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
    installation_id = asyncio.run(register(database_url, coordinator_settings))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "pi"
    stub.write_text(INTERVIEW_STUB_PI)
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
    return database_url, workspace_root, engine_factory, settings, installation_id


def create_project_and_run(client, installation_id):
    project = client.post(
        "/api/v1/projects",
        json={"display_name": "M4 Project"},
        headers={"Idempotency-Key": "m4-project"},
    ).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"objective": "build a tiny todo cli"},
        headers={"Idempotency-Key": "m4-run"},
    ).json()
    assert run["control_state"] == "QUEUED"
    assert run["engine_installation_id"] == installation_id
    return project, run


def test_question_answer_confirm_completes_the_run(tmp_path):
    database_url, workspace_root, engine_factory, settings, installation_id = (
        make_environment(tmp_path, "m4-flow")
    )
    with TestClient(create_app(settings)) as client:
        project, run = create_project_and_run(client, installation_id)

        # launch 1 asks the requirements question and releases the worker
        assert asyncio.run(execute(database_url, engine_factory)) == 1
        run_after = client.get(f"/api/v1/runs/{run['id']}").json()
        assert run_after["control_state"] == "WAITING_FOR_HUMAN"
        assert run_after["pending_interaction_id"] is not None

        open_items = client.get("/api/v1/interactions?status=OPEN").json()["items"]
        assert len(open_items) == 1
        question = open_items[0]
        assert question["run_id"] == run["id"]
        assert question["kind"] == "QUESTION"
        assert "Which UI?" in question["prompt"]
        assert question["recommendation"] == "terminal, it is the simplest."

        answer = client.post(
            f"/api/v1/interactions/{question['id']}/commands/respond",
            json={"response_type": "ANSWER", "answer": "menu bar please"},
            headers={"Idempotency-Key": "m4-answer-1"},
        )
        assert answer.status_code == 202
        retry = client.post(
            f"/api/v1/interactions/{question['id']}/commands/respond",
            json={"response_type": "ANSWER", "answer": "menu bar please"},
            headers={"Idempotency-Key": "m4-answer-1"},
        )
        assert retry.status_code == 202
        assert retry.json()["id"] == answer.json()["id"]

        resolved = client.get(f"/api/v1/interactions/{question['id']}").json()
        assert resolved["status"] == "ANSWERED"
        assert (
            client.get(f"/api/v1/runs/{run['id']}").json()["control_state"] == "QUEUED"
        )

    # the API restarts; Run state and the accepted answer are durable
    with TestClient(create_app(settings)) as restarted:
        assert (
            restarted.get(f"/api/v1/runs/{run['id']}").json()["control_state"]
            == "QUEUED"
        )

        # launch 2 applies the answer and proposes the final intent
        assert asyncio.run(execute(database_url, engine_factory)) == 1
        waiting_run = restarted.get(f"/api/v1/runs/{run['id']}").json()
        assert waiting_run["control_state"] == "WAITING_FOR_HUMAN"
        confirmation_id = waiting_run["pending_interaction_id"]
        assert confirmation_id is not None
        confirmation = restarted.get(f"/api/v1/interactions/{confirmation_id}").json()
        assert confirmation["kind"] == "FINAL_INTENT_CONFIRMATION"
        assert "tiny todo CLI" in confirmation["prompt"]

        # two different answers race: exactly one wins
        first = restarted.post(
            f"/api/v1/interactions/{confirmation_id}/commands/respond",
            json={"response_type": "REQUEST_CHANGE", "answer": "make it simpler"},
            headers={"Idempotency-Key": "m4-race-1"},
        )
        second = restarted.post(
            f"/api/v1/interactions/{confirmation_id}/commands/respond",
            json={"response_type": "CONFIRM"},
            headers={"Idempotency-Key": "m4-race-2"},
        )
        assert sorted([first.status_code, second.status_code]) == [202, 409]
        losing = second if first.status_code == 202 else first
        assert losing.json()["code"] == "INTERACTION_ALREADY_RESOLVED"

        # the accepted review request refines the summary in a new launch
        assert asyncio.run(execute(database_url, engine_factory)) == 1
        waiting_run = restarted.get(f"/api/v1/runs/{run['id']}").json()
        assert waiting_run["control_state"] == "WAITING_FOR_HUMAN"
        refined_id = waiting_run["pending_interaction_id"]
        assert refined_id is not None and refined_id != confirmation_id
        refined = restarted.get(f"/api/v1/interactions/{refined_id}").json()
        assert refined["kind"] == "FINAL_INTENT_CONFIRMATION"

        confirm = restarted.post(
            f"/api/v1/interactions/{refined_id}/commands/respond",
            json={"response_type": "CONFIRM"},
            headers={"Idempotency-Key": "m4-confirm-1"},
        )
        assert confirm.status_code == 202
        assert asyncio.run(execute(database_url, engine_factory)) == 1

        final_run = restarted.get(f"/api/v1/runs/{run['id']}").json()
        assert final_run["control_state"] == "COMPLETED"
        assert final_run["pending_interaction_id"] is None
        assert final_run["work_item_summary"] == {
            "completed": 2,
            "total": 2,
            "blocked": 0,
        }

        events = restarted.get(f"/api/v1/runs/{run['id']}/events").json()["items"]
        types = [event["event_type"] for event in events]
        assert "RUN_WAITING_FOR_HUMAN" in types
        assert "INTERACTION_RESOLVED" in types
        assert types.count("INTERACTION_OPENED") == 3
        assert types[-1] == "RUN_COMPLETED"

    workspace = workspace_root / "projects" / project["id"] / "workspace"
    transcript = (workspace / "interview_output.txt").read_text()
    assert "Q: Which UI?" in transcript
    assert "A: menu bar please" in transcript
    assert "A (refinement): make it simpler" in transcript
    accepted = [
        line for line in transcript.splitlines() if line.startswith("INTENT_FINALIZED:")
    ]
    assert len(accepted) == 1
    assert (workspace / "spec.md").is_file()
    assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"


def test_delegate_remaining_completes_autonomously(tmp_path):
    database_url, workspace_root, engine_factory, settings, installation_id = (
        make_environment(tmp_path, "m4-delegate")
    )
    with TestClient(create_app(settings)) as client:
        project, run = create_project_and_run(client, installation_id)
        assert asyncio.run(execute(database_url, engine_factory)) == 1

        question = client.get("/api/v1/interactions?status=OPEN").json()["items"][0]
        delegate = client.post(
            f"/api/v1/interactions/{question['id']}/commands/respond",
            json={"response_type": "DELEGATE_REMAINING"},
            headers={"Idempotency-Key": "m4-delegate-1"},
        )
        assert delegate.status_code == 202
        interaction = client.get(f"/api/v1/interactions/{question['id']}").json()
        assert interaction["status"] == "DELEGATED"

        # the delegated Run closes out Phase 0 and completes in one launch
        assert asyncio.run(execute(database_url, engine_factory)) == 1
        final_run = client.get(f"/api/v1/runs/{run['id']}").json()
        assert final_run["control_state"] == "COMPLETED"
        assert final_run["work_item_summary"]["total"] == 2

    workspace = workspace_root / "projects" / project["id"] / "workspace"
    transcript = (workspace / "interview_output.txt").read_text()
    assert "INTENT_FINALIZED" in transcript
    assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"
