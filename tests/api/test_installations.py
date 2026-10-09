from helpers import build_client, seed_installation


def test_list_engine_installations(client):
    response = client.get("/api/v1/engine-installations")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["engine_family"] == "SIESTA"
    assert item["engine_revision"] == "20b149e0734b09730dfd22803d2695776fcf84b8"
    assert item["adapter_version"]
    assert item["installation_digest"]
    assert item["status"] == "SUPPORTED"
    assert item["default_for_new_runs"] is True
    assert item["compatibility"] == {
        "launch": "SUPPORTED",
        "state_format": "UNKNOWN",
        "resume": "UNKNOWN",
        "security": "UNKNOWN",
        "runtime": "UNKNOWN",
    }
    assert item["capability_manifest"]["work_items"] is True
    assert item["created_at"]


def test_get_engine_installation(client):
    listed = client.get("/api/v1/engine-installations").json()["items"][0]

    response = client.get(f"/api/v1/engine-installations/{listed['id']}")

    assert response.status_code == 200
    assert response.json() == listed


def test_unknown_engine_installation_returns_problem(client):
    response = client.get("/api/v1/engine-installations/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_list_engine_installations_requires_authentication(database_url):
    seed_installation(database_url)
    client = build_client(database_url, development_mode=False, auth_mode="bearer")
    with client:
        response = client.get("/api/v1/engine-installations")

    assert response.status_code == 401
