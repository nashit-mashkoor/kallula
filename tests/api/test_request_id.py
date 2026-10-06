def test_request_id_is_generated(client):
    response = client.get("/health/live")

    assert response.headers.get("X-Request-ID")


def test_request_id_is_echoed(client):
    response = client.get("/health/live", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"
