"""Local-disk implementation of :class:`StorageService` (development default)."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from app.core.errors import NotFoundError
from app.services.storage.base import StorageService

_SAFE_KEY = re.compile(r"[^a-zA-Z0-9._/\-]")


class LocalStorage(StorageService):
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        safe = _SAFE_KEY.sub("_", key).lstrip("/")
        path = (self._base / safe).resolve()
        # Prevent path traversal outside the storage root. ``is_relative_to``
        # (Prompt 9, Phase 10) — a plain string ``startswith`` would also admit
        # sibling directories whose name merely extends the base (e.g. a key of
        # ``../<base>-secret`` resolving next to the storage root).
        if not path.is_relative_to(self._base):
            raise NotFoundError("Invalid storage key.")
        return path

    def save(self, *, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, *, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def exists(self, *, key: str) -> bool:
        return self._resolve(key).exists()

    def url(self, *, key: str) -> str:
        # App-relative reference; a real backend would return a signed URL.
        return f"/api/v1/storage/{key}"

    def delete(self, *, key: str) -> None:
        # Idempotent: a missing object is a successful no-op.
        self._resolve(key).unlink(missing_ok=True)

    def get_metadata(self, *, key: str) -> dict:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"Object not found: {key}")
        return {
            "key": key,
            "size": path.stat().st_size,
            "contentType": mimetypes.guess_type(key)[0] or "application/octet-stream",
        }
