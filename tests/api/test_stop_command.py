from helpers import fetch_events, set_run_state

from domain.states import RunControlState


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


def stop_run(client, run_id, key="stop-key"):
    return client.post(
        f"/api/v1/runs/{run_id}/commands/stop",
        json={"mode": "SAFE"},
        headers={"Idempotency-Key": key},
    )


def test_stop_accepts_and_requests_stop(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.RUNNING)

    response = stop_run(client, run["id"])

    assert response.status_code == 202
    body = response.json()
    assert body["command_type"] == "SAFE_STOP_RUN"
    assert body["target_id"] == run["id"]
    assert body["state"] == "ACCEPTED"

    run_after = client.get(f"/api/v1/runs/{run['id']}").json()
    assert run_after["control_state"] == "STOP_REQUESTED"
    events = fetch_events(database_url, run["id"])
    assert ("RUN_STOP_REQUESTED", 2, "CONTROL_PLANE") in events


def test_stop_from_waiting_for_human(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.WAITING_FOR_HUMAN)

    response = stop_run(client, run["id"])

    assert response.status_code == 202
    run_after = client.get(f"/api/v1/runs/{run['id']}").json()
    assert run_after["control_state"] == "STOP_REQUESTED"


def test_stop_is_idempotent(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.RUNNING)

    first = stop_run(client, run["id"], key="same")
    second = stop_run(client, run["id"], key="same")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_stop_requires_idempotency_key(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.RUNNING)

    response = client.post(
        f"/api/v1/runs/{run['id']}/commands/stop", json={"mode": "SAFE"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_stop_rejects_invalid_run_state(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])

    response = stop_run(client, run["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "RUN_STATE_CONFLICT"


def test_stop_rejects_unknown_run(client):
    response = stop_run(client, "does-not-exist")

    assert response.status_code == 404
