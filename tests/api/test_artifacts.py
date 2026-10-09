from helpers import seed_artifact


def create_project(client, key="project-key"):
    response = client.post(
        "/api/v1/projects",
        json={"display_name": "Expense Tracker"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def create_run(client, project_id, key="run-key"):
    response = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"objective": "Build it"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def test_artifacts_are_readable(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    artifact_id = seed_artifact(
        database_url,
        project_id=project["id"],
        run_id=run["id"],
        storage_key="spec.md",
        content="# Spec\n",
    )

    listing = client.get(f"/api/v1/runs/{run['id']}/artifacts")

    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == artifact_id
    assert items[0]["artifact_class"] == "SPECIFICATION"
    assert items[0]["display_name"] == "Specification"
    assert items[0]["storage_kind"] == "WORKSPACE_REFERENCE"
    assert "storage_key" not in items[0]

    fetched = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["id"]

    content = client.get(f"/api/v1/artifacts/{artifact_id}/content")
    assert content.status_code == 200
    assert content.text == "# Spec\n"
    assert content.headers["content-type"].startswith("text/markdown")


def test_artifact_content_rejects_path_escape(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    artifact_id = seed_artifact(
        database_url,
        project_id=project["id"],
        run_id=run["id"],
        storage_key="../outside.txt",
    )

    content = client.get(f"/api/v1/artifacts/{artifact_id}/content")

    assert content.status_code == 404


def test_unknown_artifact_returns_problem(client):
    response = client.get("/api/v1/artifacts/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
