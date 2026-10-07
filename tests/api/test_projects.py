from helpers import build_client


def create_project(client, key="key-1", name="Expense Tracker"):
    return client.post(
        "/api/v1/projects",
        json={"display_name": name},
        headers={"Idempotency-Key": key},
    )


def test_create_project_returns_created_project(client):
    response = create_project(client)

    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Expense Tracker"
    assert body["origin"]["type"] == "NEW_IDEA"
    assert body["workspace_status"] == "READY"
    assert body["version"] == 1
    assert response.headers["ETag"] == '"v1"'


def test_create_project_is_idempotent(client):
    first = create_project(client, key="same")
    second = create_project(client, key="same")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listing = client.get("/api/v1/projects").json()
    assert len(listing["items"]) == 1


def test_create_project_with_reused_key_and_different_body_conflicts(client):
    create_project(client, key="k", name="One")

    response = create_project(client, key="k", name="Two")

    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_create_project_requires_idempotency_key(client):
    response = client.post("/api/v1/projects", json={"display_name": "X"})

    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_get_and_list_projects(client):
    created = create_project(client).json()

    got = client.get(f"/api/v1/projects/{created['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]
    assert got.headers["ETag"] == '"v1"'

    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == created["id"]


def test_unknown_project_returns_problem(client):
    response = client.get("/api/v1/projects/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_patch_updates_display_name_and_version(client):
    created = create_project(client).json()

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"display_name": "Renamed"},
        headers={"If-Match": '"v1"'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Renamed"
    assert body["version"] == 2
    assert response.headers["ETag"] == '"v2"'


def test_patch_requires_if_match(client):
    created = create_project(client).json()

    response = client.patch(
        f"/api/v1/projects/{created['id']}", json={"display_name": "X"}
    )

    assert response.status_code == 428
    assert response.json()["code"] == "PRECONDITION_REQUIRED"


def test_patch_with_stale_etag_fails(client):
    created = create_project(client).json()
    client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"display_name": "First"},
        headers={"If-Match": '"v1"'},
    )

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"display_name": "Second"},
        headers={"If-Match": '"v1"'},
    )

    assert response.status_code == 412
    assert response.json()["code"] == "PRECONDITION_FAILED"


def test_projects_require_authentication(database_url):
    with build_client(database_url, development_mode=False) as test_client:
        response = test_client.get("/api/v1/projects")

    assert response.status_code == 401
