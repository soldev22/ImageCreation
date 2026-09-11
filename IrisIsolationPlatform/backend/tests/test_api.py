import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.vercel import app as vercel_app


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


def test_stateless_isolation_returns_png() -> None:
    image = np.full((320, 320, 3), 235, dtype=np.uint8)
    cv2.circle(image, (160, 160), 105, (65, 95, 125), -1)
    cv2.circle(image, (160, 160), 38, (5, 5, 5), -1)
    encoded, buffer = cv2.imencode(".jpg", image)
    assert encoded

    with TestClient(vercel_app) as client:
        response = client.post(
            "/api/v1/isolate",
            files={"file": ("eye.jpg", buffer.tobytes(), "image/jpeg")},
            data={"method": "opencv"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert int(response.headers["X-Image-Width"]) > 0
    assert int(response.headers["X-Image-Height"]) > 0
    assert response.content.startswith(b"\x89PNG")