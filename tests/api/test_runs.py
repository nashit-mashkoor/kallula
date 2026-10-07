def create_project(client, key="project-key"):
    response = client.post(
        "/api/v1/projects",
        json={"display_name": "Expense Tracker"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()


def create_run(client, project_id, key="run-key", objective="Build it"):
    return client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"objective": objective},
        headers={"Idempotency-Key": key},
    )


def test_create_run_starts_queued(client):
    project = create_project(client)

    response = create_run(client, project["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["control_state"] == "QUEUED"
    assert body["ordinal"] == 1
    assert body["objective"] == "Build it"
    assert body["effective_config_snapshot_id"]
    assert response.headers["ETag"] == '"v1"'


def test_create_run_is_idempotent(client):
    project = create_project(client)

    first = create_run(client, project["id"], key="same")
    second = create_run(client, project["id"], key="same")

    assert first.json()["id"] == second.json()["id"]
    listing = client.get(f"/api/v1/projects/{project['id']}/runs").json()
    assert len(listing["items"]) == 1


def test_create_run_requires_idempotency_key(client):
    project = create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"objective": "x"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_create_run_for_unknown_project(client):
    response = create_run(client, "does-not-exist")

    assert response.status_code == 404


def test_get_run_and_configuration(client):
    project = create_project(client)
    run = create_run(client, project["id"]).json()

    got = client.get(f"/api/v1/runs/{run['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == run["id"]

    config = client.get(f"/api/v1/runs/{run['id']}/configuration")
    assert config.status_code == 200
    cfg = config.json()
    assert cfg["run_id"] == run["id"]
    assert cfg["content_hash"]
    assert cfg["agent_profile_version_id"] is None

    project_after = client.get(f"/api/v1/projects/{project['id']}").json()
    assert project_after["current_run_id"] == run["id"]


def test_second_run_gets_next_ordinal(client):
    project = create_project(client)

    create_run(client, project["id"], key="r1")
    second = create_run(client, project["id"], key="r2").json()

    assert second["ordinal"] == 2


def test_unknown_run_returns_problem(client):
    response = client.get("/api/v1/runs/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
