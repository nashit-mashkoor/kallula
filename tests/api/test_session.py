from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings


def test_session_returns_development_principal(client):
    response = client.get("/api/v1/session")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "principal": {
            "id": "dev-principal",
            "display_name": "Development User",
            "email": "dev@kallula.local",
        },
        "session_expires_at": None,
    }


def test_session_is_unauthenticated_outside_development_mode(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'session.db'}",
        log_level="WARNING",
        _env_file=None,
        development_mode=False,
    )

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/api/v1/session")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "principal": None,
        "session_expires_at": None,
    }
