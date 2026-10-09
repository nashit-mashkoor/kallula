import asyncio
import os

from fastapi.testclient import TestClient
from test_real_engine_run import STUB_PI, VENDOR_FACTORY

from api.main import create_app
from api.settings import Settings
from coordinator.engines import build_engine_factory, register_pinned_installation
from coordinator.loop import process_queued_runs
from coordinator.settings import CoordinatorSettings
from persistence.base import Base
from persistence.db import create_db_engine, create_session_factory

VENDOR_REVISION = "20b149e0734b09730dfd22803d2695776fcf84b8"


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
                session, holder_id="dod", engine_factory=engine_factory
            )
    finally:
        await engine.dispose()


def test_definition_of_done_flow(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'dod.db'}"
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
    stub.write_text(STUB_PI)
    stub.chmod(0o755)
    (bin_dir / "scenario").write_text("pass")
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

    with TestClient(create_app(settings)) as client:
        project_response = client.post(
            "/api/v1/projects",
            json={"display_name": "DoD Project"},
            headers={"Idempotency-Key": "dod-project"},
        )
        assert project_response.status_code == 201
        project = project_response.json()
        assert project["workspace_status"] == "READY"

        run_response = client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={"objective": "build a tiny todo cli"},
            headers={"Idempotency-Key": "dod-run"},
        )
        assert run_response.status_code == 201
        run = run_response.json()
        assert run["control_state"] == "QUEUED"
        assert run["engine_installation_id"] == installation_id

        assert asyncio.run(execute(database_url, engine_factory)) == 1

        run_after = client.get(f"/api/v1/runs/{run['id']}").json()
        assert run_after["control_state"] == "COMPLETED"
        assert run_after["stage"]["category"] == "LEARNING"
        assert run_after["work_item_summary"] == {
            "completed": 2,
            "total": 2,
            "blocked": 0,
        }

        work_items = client.get(f"/api/v1/runs/{run['id']}/work-items").json()["items"]
        assert [item["title"] for item in work_items] == ["Add hello", "Add bye"]
        assert {item["state"] for item in work_items} == {"COMPLETED"}

        artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()["items"]
        classes = {artifact["artifact_class"] for artifact in artifacts}
        assert {
            "SPECIFICATION",
            "PLAN",
            "TEST_EVIDENCE",
            "VERIFICATION_EVIDENCE",
        } <= classes

        events = client.get(f"/api/v1/runs/{run['id']}/events").json()["items"]
        engine_types = {
            event["event_type"]
            for event in events
            if event["source"] == "ENGINE_ADAPTER"
        }
        assert {
            "STAGE_STARTED",
            "STAGE_COMPLETED",
            "WORK_ITEM_COMPLETED",
            "VERIFICATION_COMPLETED",
            "ARTIFACT_DISCOVERED",
        } <= engine_types

        configuration = client.get(f"/api/v1/runs/{run['id']}/configuration").json()
        installation = configuration["engine_installation"]
        assert installation["engine_family"] == "SIESTA"
        assert installation["engine_revision"] == VENDOR_REVISION
        assert installation["status"] == "SUPPORTED"

    workspace = workspace_root / "projects" / project["id"] / "workspace"
    assert (workspace / "spec.md").is_file()
    assert (workspace / "issues.md").is_file()
    assert (workspace / "verify_verdict.txt").read_text().strip() == "VERIFY_PASSED"
