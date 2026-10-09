from helpers import seed_work_item

from domain.states import WorkItemState


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


def test_work_items_are_readable(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    first = seed_work_item(
        database_url, run["id"], engine_key="issue:1", ordinal=1, title="Add hello"
    )
    second = seed_work_item(
        database_url,
        run["id"],
        engine_key="issue:2",
        ordinal=2,
        title="Add bye",
        state=WorkItemState.BLOCKED,
    )

    listing = client.get(f"/api/v1/runs/{run['id']}/work-items")

    assert listing.status_code == 200
    items = listing.json()["items"]
    assert [item["engine_key"] for item in items] == ["issue:1", "issue:2"]
    assert items[0]["id"] == first
    assert items[1]["id"] == second
    assert items[1]["state"] == "BLOCKED"
    assert items[0]["acceptance_criteria"] == []
    assert items[0]["attempt_count"] == 0

    fetched = client.get(f"/api/v1/work-items/{second}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Add bye"


def test_run_exposes_work_item_summary(client, database_url):
    project = create_project(client)
    run = create_run(client, project["id"])
    seed_work_item(
        database_url,
        run["id"],
        engine_key="issue:1",
        ordinal=1,
        state=WorkItemState.COMPLETED,
    )
    seed_work_item(
        database_url,
        run["id"],
        engine_key="issue:2",
        ordinal=2,
        state=WorkItemState.BLOCKED,
    )
    seed_work_item(
        database_url,
        run["id"],
        engine_key="issue:3",
        ordinal=3,
        state=WorkItemState.ACTIVE,
    )

    fetched = client.get(f"/api/v1/runs/{run['id']}").json()

    assert fetched["work_item_summary"] == {
        "completed": 1,
        "total": 3,
        "blocked": 1,
    }


def test_list_work_items_for_unknown_run(client):
    response = client.get("/api/v1/runs/does-not-exist/work-items")

    assert response.status_code == 404


def test_unknown_work_item_returns_problem(client):
    response = client.get("/api/v1/work-items/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
