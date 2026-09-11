import asyncio
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.core.config import Settings, get_settings
from app.core.security import Principal, require_principal
from app.models.segmentation import OpenCVIrisSegmenter
from app.models.unet import UNetIrisSegmenter

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

router = APIRouter(prefix="/api/v1")


def create_segmenter(method: str, settings: Settings):
    if method == "opencv":
        return OpenCVIrisSegmenter()
    if method == "unet" and settings.unet_checkpoint:
        return UNetIrisSegmenter(settings.unet_checkpoint)
    raise HTTPException(status_code=503, detail="U-Net checkpoint is not configured")


@router.post("/isolate", tags=["images"])
async def isolate_image(
    file: Annotated[UploadFile, File()],
    _principal: Annotated[Principal, Depends(require_principal)],
    method: Annotated[str, Form()] = "opencv",
) -> Response:
    settings = get_settings()
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="JPEG, PNG, or WebP required",
        )
    if method not in {"opencv", "unet"}:
        raise HTTPException(status_code=422, detail="Method must be opencv or unet")

    content = await file.read(settings.serverless_max_file_bytes + 1)
    if len(content) > settings.serverless_max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds the 4 MB serverless upload limit",
        )
    if not content:
        raise HTTPException(status_code=422, detail="Image is empty")

    try:
        output = await asyncio.to_thread(create_segmenter(method, settings).segment, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(output.png) > settings.serverless_max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Isolated PNG exceeds the 4 MB serverless response limit",
        )

    safe_stem = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "iris")[:100]
    return Response(
        content=output.png,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="isolated-{safe_stem}.png"',
            "X-Image-Id": str(uuid.uuid4()),
            "X-Image-Width": str(output.width),
            "X-Image-Height": str(output.height),
            "X-Confidence-Score": str(output.confidence),
        },
    )