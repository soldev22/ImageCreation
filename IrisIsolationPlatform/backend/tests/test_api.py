from fastapi.testclient import TestClient

from app.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_invalid_content_type_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/images",
            files={"file": ("payload.txt", b"not an image", "text/plain")},
            data={"method": "opencv"},
        )
    assert response.status_code == 415