# REST API Contract

Base path: `/api/v1`

All processing and result endpoints require `Authorization: Bearer <JWT>`. Responses include `X-Correlation-ID`. Errors use RFC 9457-style problem details.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Process liveness; no dependency checks |
| `GET` | `/health/ready` | Database and storage readiness |
| `POST` | `/images` | Upload and segment one image |
| `POST` | `/images/batch` | Upload and segment a bounded image batch |
| `GET` | `/images/{image_id}` | Retrieve owned image metadata |
| `GET` | `/images/{image_id}/result` | Download the transparent PNG result |

## Single Image

`POST /api/v1/images` uses `multipart/form-data`:

- `file`: JPEG, PNG, or WebP image.
- `method`: `opencv` (default) or `unet`.

Success (`201 Created`):

```json
{
  "id": "c83c5b0d-b401-43a0-b3f1-56959989000f",
  "filename": "eye.jpg",
  "status": "completed",
  "method": "opencv",
  "confidenceScore": 0.91,
  "width": 1600,
  "height": 900,
  "resultUrl": "/api/v1/images/c83c5b0d-b401-43a0-b3f1-56959989000f/result",
  "createdAt": "2026-09-11T12:00:00Z"
}
```

## Batch Images

`POST /api/v1/images/batch` accepts repeated `files` parts and one `method`. The configured default maximum is 10 files. A `207 Multi-Status` response contains one success or problem object per upload.

## Problems

```json
{
  "type": "https://iris.example/problems/invalid-image",
  "title": "Invalid image",
  "status": 422,
  "detail": "The upload could not be decoded as JPEG, PNG, or WebP.",
  "correlationId": "01J7H5Z4J4D3M7H2FMF1T1K6FY"
}
```

Common statuses are `401`, `403`, `404`, `413`, `415`, `422`, `429`, and `500`.

## Authentication

Production validates externally issued JWT access tokens with configured issuer, audience, and JWKS URL. Local development may enable `AUTH_MODE=development` and request a short-lived token from the documented developer command; that mode must never be enabled in a production environment.
