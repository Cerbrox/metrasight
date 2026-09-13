"""Storage subpackage."""
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorage

__all__ = ["StorageService", "LocalStorage"]
