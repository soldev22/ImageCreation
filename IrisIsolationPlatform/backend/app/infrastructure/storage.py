from pathlib import Path
from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from app.core.config import Settings


class ObjectStorage(Protocol):
    async def put(self, path: str, data: bytes, content_type: str) -> None: ...
    async def get(self, path: str) -> bytes: ...
    async def ready(self) -> bool: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _safe_path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Invalid storage path")
        return candidate

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def get(self, path: str) -> bytes:
        return self._safe_path(path).read_bytes()

    async def ready(self) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root.is_dir()


class AzureBlobStorage:
    def __init__(self, account_url: str, container: str) -> None:
        self.credential = DefaultAzureCredential()
        self.client = BlobServiceClient(account_url, credential=self.credential).get_container_client(container)

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        await self.client.upload_blob(path, data, overwrite=True)

    async def get(self, path: str) -> bytes:
        return await (await self.client.download_blob(path)).readall()

    async def ready(self) -> bool:
        try:
            await self.client.get_container_properties()
            return True
        except Exception:
            return False


def create_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "azure":
        if not settings.azure_storage_account_url:
            raise RuntimeError("IRIS_AZURE_STORAGE_ACCOUNT_URL is required")
        return AzureBlobStorage(settings.azure_storage_account_url, settings.azure_storage_container)
    return LocalStorage(settings.storage_path)