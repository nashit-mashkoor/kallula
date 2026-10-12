from helpers import seed_attempt

from domain.states import AttemptState


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


def test_attempts_are_readable(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    first = seed_attempt(
        database_url,
        run["id"],
        ordinal=1,
        state=AttemptState.EXITED,
        terminal_reason="SAFE_STOP",
    )
    second = seed_attempt(
        database_url,
        run["id"],
        ordinal=2,
        state=AttemptState.LOST,
        terminal_reason="PROCESS_LOST",
    )

    response = client.get(f"/api/v1/runs/{run['id']}/attempts")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [first, second]
    assert [item["ordinal"] for item in items] == [1, 2]
    assert [item["state"] for item in items] == ["EXITED", "LOST"]
    assert [item["terminal_reason"] for item in items] == [
        "SAFE_STOP",
        "PROCESS_LOST",
    ]
    assert "worker_runtime_ref" not in items[0]


def test_attempts_for_unknown_run(client):
    response = client.get("/api/v1/runs/does-not-exist/attempts")

    assert response.status_code == 404
