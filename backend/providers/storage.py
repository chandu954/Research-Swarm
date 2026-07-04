"""Local filesystem storage provider."""
from __future__ import annotations
import os
from loguru import logger

from backend.core.plugin import PluginSpec
from backend.core.providers.storage import StorageProvider


UPLOAD_DIR = "./data/uploads"


class LocalStorageProvider(StorageProvider):
    spec = PluginSpec(
        name="local",
        description="Local filesystem storage for uploaded files",
        version="1.0.0",
    )

    def __init__(self) -> None:
        self._base_path: str = ""

    async def initialize(self) -> None:
        self._base_path = os.getenv("UPLOAD_DIR", UPLOAD_DIR)
        os.makedirs(self._base_path, exist_ok=True)
        logger.info(f"LocalStorageProvider initialized at {self._base_path}")

    async def cleanup(self) -> None:
        pass

    async def save(self, path: str, content: bytes) -> str:
        full_path = os.path.join(self._base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return full_path

    async def load(self, path: str) -> bytes | None:
        full_path = os.path.join(self._base_path, path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "rb") as f:
            return f.read()

    async def delete(self, path: str) -> bool:
        full_path = os.path.join(self._base_path, path)
        if not os.path.exists(full_path):
            return False
        os.remove(full_path)
        return True

    async def exists(self, path: str) -> bool:
        return os.path.exists(os.path.join(self._base_path, path))
