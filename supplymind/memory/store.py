"""
Memory Store — abstract storage backend with JSON file and SQLite implementations.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryStore(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        ...

    @abstractmethod
    def set(self, key: str, value: Any):
        ...

    @abstractmethod
    def delete(self, key: str):
        ...

    @abstractmethod
    def keys(self) -> list[str]:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...


class JSONFileStore(MemoryStore):
    """Simple JSON file-based memory store.

    Each key maps to a separate JSON file (or all in one file).
    """

    def __init__(self, base_dir: str = ".supplymind/store"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        # Sanitize key for use as filename
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.base_dir / f"{safe_key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path_for_key(key)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {path}: {e}")
        return None

    def set(self, key: str, value: Any):
        path = self._path_for_key(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False, default=str)

    def delete(self, key: str):
        path = self._path_for_key(key)
        if path.exists():
            path.unlink()

    def keys(self) -> list[str]:
        return [f.stem for f in self.base_dir.glob("*.json")]

    def exists(self, key: str) -> bool:
        return self._path_for_key(key).exists()
