"""
HITL Session Store — JSON file-based persistence for HITL sessions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STORE_DIR = ".supplymind/hitl_sessions"


class JSONFileStore:
    """Persist HITL sessions to JSON files on disk.

    Each session is stored as a separate JSON file keyed by session ID.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or DEFAULT_STORE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, data: dict):
        path = self.base_dir / f"{session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load(self, session_id: str) -> dict | None:
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load session {session_id}: {e}")
            return None

    def delete(self, session_id: str):
        path = self.base_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()

    def load_all(self) -> dict[str, dict]:
        results = {}
        for path in self.base_dir.glob("hitl_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sid = data.get("id", path.stem)
                    results[sid] = data
            except (json.JSONDecodeError, IOError):
                continue
        return results
