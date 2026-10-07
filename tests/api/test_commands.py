from helpers import seed_command


def test_command_can_be_read(client, database_url):
    command_id = seed_command(database_url)

    response = client.get(f"/api/v1/commands/{command_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == command_id
    assert body["state"] == "ACCEPTED"
    assert body["target_id"] == "run-1"
    assert body["failure"] is None


def test_unknown_command_returns_problem(client):
    response = client.get("/api/v1/commands/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
