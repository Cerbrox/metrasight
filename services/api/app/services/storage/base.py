"""Storage abstraction (S3-compatible seam).

The rest of the system only knows this interface, so the local-disk backend used
in development can be replaced by an S3/MinIO backend later via configuration.
"""
from __future__ import annotations

import abc


class StorageService(abc.ABC):
    @abc.abstractmethod
    def save(self, *, key: str, data: bytes, content_type: str | None = None) -> str:
        """Persist bytes under ``key`` and return the canonical storage key."""

    @abc.abstractmethod
    def read(self, *, key: str) -> bytes: ...

    @abc.abstractmethod
    def exists(self, *, key: str) -> bool: ...

    @abc.abstractmethod
    def url(self, *, key: str) -> str:
        """A retrievable/reference URL for the object (may be app-relative)."""

    @abc.abstractmethod
    def delete(self, *, key: str) -> None:
        """Remove the object at ``key``. Idempotent — a missing key is a no-op."""

    @abc.abstractmethod
    def get_metadata(self, *, key: str) -> dict:
        """Return safe object metadata: ``{"key", "size", "contentType"}``.

        Never exposes the absolute server path — only the logical storage key.
        """
