import asyncio

from helpers import build_client, workspace_root_for

from coordinator.loop import process_queued_runs
from engine.fake import FakeEngine
from persistence.db import create_db_engine, create_session_factory


def create_project(client, key="workspace-key"):
    response = client.post(
        "/api/v1/projects",
        json={"display_name": "Expense Tracker"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def create_run(client, project_id, key="run-key"):
    return client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"objective": "Build it"},
        headers={"Idempotency-Key": key},
    )


async def drive_runs(database_url: str) -> int:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            return await process_queued_runs(
                session, holder_id="test", engine_factory=FakeEngine
            )
    finally:
        await engine.dispose()


def workspace_path(database_url: str, project_id: str):
    return workspace_root_for(database_url) / "projects" / project_id / "workspace"


def test_project_creation_allocates_workspace(client, database_url):
    project = create_project(client)

    workspace = workspace_path(database_url, project["id"])

    assert project["workspace_status"] == "READY"
    assert workspace.is_dir()
    assert (workspace / ".git").exists()


def test_workspace_survives_attempt_exit(client, database_url):
    project = create_project(client)
    workspace = workspace_path(database_url, project["id"])
    run = create_run(client, project["id"])
    assert run.status_code == 201

    assert asyncio.run(drive_runs(database_url)) == 1

    assert workspace.is_dir()
    assert (workspace / ".git").exists()
    project_after = client.get(f"/api/v1/projects/{project['id']}").json()
    assert project_after["workspace_status"] == "READY"


def test_project_creation_fails_when_workspace_root_unusable(database_url, tmp_path):
    blocked = tmp_path / "blocked-root"
    blocked.write_text("not a directory")
    with build_client(database_url, workspace_root=blocked) as client:
        response = client.post(
            "/api/v1/projects",
            json={"display_name": "Expense Tracker"},
            headers={"Idempotency-Key": "blocked-key"},
        )
        listing = client.get("/api/v1/projects").json()

    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert listing["items"] == []
