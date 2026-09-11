import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ImageResponse
from app.application.image_service import ImageService
from app.core.config import Settings, get_settings
from app.core.security import Principal, require_principal
from app.infrastructure.database import ImageRecord, database_ready, get_session
from app.infrastructure.storage import ObjectStorage, create_storage
from app.models.segmentation import OpenCVIrisSegmenter
from app.models.unet import UNetIrisSegmenter

router = APIRouter(prefix="/api/v1")


def get_storage(settings: Settings = Depends(get_settings)) -> ObjectStorage:
    return create_storage(settings)


def create_segmenter(method: str, settings: Settings):
    if method == "opencv":
        return OpenCVIrisSegmenter()
    if method == "unet" and settings.unet_checkpoint:
        return UNetIrisSegmenter(settings.unet_checkpoint)
    raise HTTPException(status_code=503, detail="U-Net checkpoint is not configured")


def response_for(record: ImageRecord) -> ImageResponse:
    return ImageResponse(
        id=record.id, filename=record.filename, status=record.status,
        method=record.segmentation_method, confidence_score=record.confidence_score or 0,
        width=record.width or 0, height=record.height or 0,
        result_url=f"/api/v1/images/{record.id}/result", created_at=record.upload_date,
    )


@router.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/ready", tags=["health"])
async def ready(session: AsyncSession = Depends(get_session), storage: ObjectStorage = Depends(get_storage)) -> Response:
    healthy = await database_ready(session) and await storage.ready()
    return Response(content='{"status":"ready"}' if healthy else '{"status":"unavailable"}', media_type="application/json", status_code=200 if healthy else 503)


@router.post("/images", response_model=ImageResponse, response_model_by_alias=True, status_code=201, tags=["images"])
async def create_image(
    file: Annotated[UploadFile, File()], method: Annotated[str, Form()] = "opencv",
    principal: Principal = Depends(require_principal), session: AsyncSession = Depends(get_session),
    storage: ObjectStorage = Depends(get_storage), settings: Settings = Depends(get_settings),
) -> ImageResponse:
    if method not in {"opencv", "unet"}:
        raise HTTPException(status_code=422, detail="Method must be opencv or unet")
    record = await ImageService(session, storage, create_segmenter(method, settings), settings).process(file, method, principal.subject, str(uuid.uuid4()))
    return response_for(record)


@router.post("/images/batch", response_model=list[ImageResponse], response_model_by_alias=True, status_code=207, tags=["images"])
async def create_batch(
    files: Annotated[list[UploadFile], File()], method: Annotated[str, Form()] = "opencv",
    principal: Principal = Depends(require_principal), session: AsyncSession = Depends(get_session),
    storage: ObjectStorage = Depends(get_storage), settings: Settings = Depends(get_settings),
) -> list[ImageResponse]:
    if len(files) > settings.max_batch_size:
        raise HTTPException(status_code=413, detail=f"Batch is limited to {settings.max_batch_size} files")
    if method not in {"opencv", "unet"}:
        raise HTTPException(status_code=422, detail="Method must be opencv or unet")
    service = ImageService(session, storage, create_segmenter(method, settings), settings)
    return [response_for(await service.process(item, method, principal.subject, str(uuid.uuid4()))) for item in files]


@router.get("/images/{image_id}", response_model=ImageResponse, response_model_by_alias=True, tags=["images"])
async def get_image(image_id: str, principal: Principal = Depends(require_principal), session: AsyncSession = Depends(get_session)) -> ImageResponse:
    record = await session.scalar(select(ImageRecord).where(ImageRecord.id == image_id, ImageRecord.owner_subject == principal.subject))
    if record is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return response_for(record)


@router.get("/images/{image_id}/result", tags=["images"])
async def get_result(image_id: str, principal: Principal = Depends(require_principal), session: AsyncSession = Depends(get_session), storage: ObjectStorage = Depends(get_storage)) -> StreamingResponse:
    record = await session.scalar(select(ImageRecord).where(ImageRecord.id == image_id, ImageRecord.owner_subject == principal.subject))
    if record is None or record.extracted_path is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return StreamingResponse(iter([await storage.get(record.extracted_path)]), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="iris-{image_id}.png"'})