import asyncio
import hashlib
import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.database import AuditEvent, ImageRecord
from app.infrastructure.storage import ObjectStorage
from app.models.segmentation import IrisSegmenter

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage, segmenter: IrisSegmenter, settings: Settings) -> None:
        self.session, self.storage, self.segmenter, self.settings = session, storage, segmenter, settings

    async def process(self, upload: UploadFile, method: str, owner: str, correlation_id: str) -> ImageRecord:
        if upload.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="JPEG, PNG, or WebP required")
        content = await upload.read(self.settings.max_file_bytes + 1)
        if len(content) > self.settings.max_file_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image exceeds maximum file size")
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image is empty")

        image_id = str(uuid.uuid4())
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[upload.content_type]
        original_path = f"originals/{owner}/{image_id}.{extension}"
        extracted_path = f"results/{owner}/{image_id}.png"
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", upload.filename or f"upload.{extension}")[:255]
        await self.storage.put(original_path, content, upload.content_type)
        try:
            output = await asyncio.to_thread(self.segmenter.segment, content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        await self.storage.put(extracted_path, output.png, "image/png")
        record = ImageRecord(
            id=image_id, filename=safe_name, content_type=upload.content_type,
            upload_date=datetime.now(UTC), status="completed", segmentation_method=method,
            confidence_score=output.confidence, original_path=original_path,
            extracted_path=extracted_path, owner_subject=owner, sha256=hashlib.sha256(content).hexdigest(),
            width=output.width, height=output.height,
        )
        self.session.add(record)
        self.session.add(AuditEvent(actor_subject=owner, action="image.segment", image_id=image_id, outcome="success", correlation_id=correlation_id, details={"method": method}))
        await self.session.commit()
        return record