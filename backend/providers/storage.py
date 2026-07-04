"""Local filesystem storage provider."""
from __future__ import annotations
import os
from pathlib import Path
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
        self._base_path: Path = Path()

    async def initialize(self) -> None:
        raw = os.getenv("UPLOAD_DIR", UPLOAD_DIR)
        self._base_path = Path(raw).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageProvider initialized at {self._base_path}")

    async def cleanup(self) -> None:
        pass

    def _resolve(self, path: str) -> Path:
        """Resolve a user-supplied path safely within the base directory."""
        joined = (self._base_path / path).resolve()
        if not str(joined).startswith(str(self._base_path)):
            raise PermissionError(f"Path traversal denied: {path}")
        return joined

    async def save(self, path: str, content: bytes) -> str:
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(full_path)

    async def load(self, path: str) -> bytes | None:
        full_path = self._resolve(path)
        if not full_path.exists():
            return None
        return full_path.read_bytes()

    async def delete(self, path: str) -> bool:
        full_path = self._resolve(path)
        if not full_path.exists():
            return False
        full_path.unlink()
        return True

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()
