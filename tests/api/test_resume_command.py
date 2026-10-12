from helpers import fetch_events, set_run_state

from domain.states import Recoverability, RunControlState


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


def resume_run(client, run_id, key="resume-key"):
    return client.post(
        f"/api/v1/runs/{run_id}/commands/resume",
        json={"reason": "USER_REQUEST"},
        headers={"Idempotency-Key": key},
    )


def test_resume_moves_stopped_run_to_queued(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.STOPPED)

    before = client.get(f"/api/v1/runs/{run['id']}").json()
    assert before["recovery"] == {"resume_allowed": True, "reason": None}

    response = resume_run(client, run["id"])

    assert response.status_code == 202
    body = response.json()
    assert body["command_type"] == "RESUME_RUN"
    assert body["state"] == "APPLIED"
    assert body["applied_at"] is not None

    run_after = client.get(f"/api/v1/runs/{run['id']}").json()
    assert run_after["control_state"] == "QUEUED"
    events = fetch_events(database_url, run["id"])
    assert ("RUN_QUEUED", 2, "CONTROL_PLANE") in events


def test_resume_failed_resumable_run(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(
        database_url,
        run["id"],
        RunControlState.FAILED,
        recoverability=Recoverability.RESUMABLE,
    )

    response = resume_run(client, run["id"])

    assert response.status_code == 202
    run_after = client.get(f"/api/v1/runs/{run['id']}").json()
    assert run_after["control_state"] == "QUEUED"


def test_resume_rejects_failed_not_resumable(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(
        database_url,
        run["id"],
        RunControlState.FAILED,
        recoverability=Recoverability.UNKNOWN,
    )

    response = resume_run(client, run["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "RESUME_INCOMPATIBLE"


def test_resume_rejects_active_run(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.RUNNING)

    response = resume_run(client, run["id"])

    assert response.status_code == 409
    assert response.json()["code"] == "RESUME_INCOMPATIBLE"


def test_resume_requires_idempotency_key(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.STOPPED)

    response = client.post(
        f"/api/v1/runs/{run['id']}/commands/resume", json={"reason": "USER_REQUEST"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_resume_is_idempotent(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.STOPPED)

    first = resume_run(client, run["id"], key="same")
    second = resume_run(client, run["id"], key="same")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_resume_compatibility_reports_blocked_states(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    set_run_state(database_url, run["id"], RunControlState.RUNNING)

    response = client.get(f"/api/v1/runs/{run['id']}/resume-compatibility")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNSUPPORTED"
    assert body["allowed_action"] is None
    assert body["reason"]

    set_run_state(database_url, run["id"], RunControlState.STOPPED)
    allowed = client.get(f"/api/v1/runs/{run['id']}/resume-compatibility").json()
    assert allowed["status"] == "SUPPORTED"
    assert allowed["allowed_action"] == "RESUME"
    assert allowed["engine_installation"]["engine_family"] == "SIESTA"
