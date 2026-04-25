"""
Working Memory — session-scoped, ephemeral context storage.

Stores current session state, pipeline intermediate results,
and transient computation data. Destroyed when session ends.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WorkingMemory:
    """In-memory, session-scoped working memory.

    This is a simple key-value store that lives for the duration of
    a single pipeline execution or agent conversation.
    """

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._created_at: float = time.time()
        self._session_id: str = f"session_{int(self._created_at * 1000)}"

    @property
    def session_id(self) -> str:
        return self._session_id

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key."""
        return self._store.get(key, default)

    def set(self, key: str, value: Any):
        """Store a value."""
        self._store[key] = value
        logger.debug(f"WorkingMemory[{self.session_id}]: set '{key}'")

    def delete(self, key: str):
        """Remove a key."""
        if key in self._store:
            del self._store[key]

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def items(self) -> list[tuple[str, Any]]:
        return list(self._store.items())

    def clear(self):
        """Clear all data (end of session)."""
        self._store.clear()
        logger.debug(f"WorkingMemory[{self.session_id}]: cleared")

    def to_dict(self) -> dict:
        """Export all contents as a plain dict."""
        return dict(self._store)

    @property
    def size(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __repr__(self) -> str:
        return f"WorkingMemory(session={self.session_id}, items={len(self._store)})"
