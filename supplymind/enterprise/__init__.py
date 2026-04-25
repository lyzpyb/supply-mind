"""
Audit Log — structured, append-only audit trail for enterprise compliance.

Records all skill executions, HITL decisions, pipeline runs, and
configuration changes with timestamps, user context, and rationale.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = ".supplymind/audit"


class AuditEventType(str, Enum):
    SKILL_EXECUTION = "skill_execution"
    PIPELINE_RUN = "pipeline_run"
    HITL_DECISION = "hitl_decision"
    CONFIG_CHANGE = "config_change"
    DATA_ACCESS = "data_access"
    ERROR = "error"


@dataclass
class AuditEvent:
    """A single audit log entry."""
    event_type: AuditEventType
    timestamp: str = ""
    actor: str = "system"
    skill: str = ""
    action: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    outcome: str = "success"
    duration_ms: float = 0.0
    session_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuditLogger:
    """Append-only audit logger writing JSONL to disk.

    Thread-safe. Each log entry is a single JSON line for easy parsing
    and ingestion into SIEM/log aggregation systems.
    """

    def __init__(self, audit_dir: str | None = None):
        self._dir = Path(audit_dir or DEFAULT_AUDIT_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_file = self._dir / f"audit_{datetime.now(timezone.utc).strftime('%Y%m')}.jsonl"

    def log(self, event: AuditEvent):
        """Append an audit event to the log."""
        entry = {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp,
            "actor": event.actor,
            "skill": event.skill,
            "action": event.action,
            "detail": event.detail,
            "outcome": event.outcome,
            "duration_ms": event.duration_ms,
            "session_id": event.session_id,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"

        with self._lock:
            with open(self._current_file, "a", encoding="utf-8") as f:
                f.write(line)

    def log_skill_execution(
        self,
        skill: str,
        arguments: dict[str, Any],
        outcome: str = "success",
        duration_ms: float = 0.0,
        actor: str = "system",
        error: str | None = None,
    ):
        detail = {"arguments_keys": list(arguments.keys())}
        if error:
            detail["error"] = error[:500]
        self.log(AuditEvent(
            event_type=AuditEventType.SKILL_EXECUTION,
            actor=actor,
            skill=skill,
            action="execute",
            detail=detail,
            outcome=outcome,
            duration_ms=duration_ms,
        ))

    def log_hitl_decision(
        self,
        session_id: str,
        skill: str,
        decision: str,
        reason: str = "",
        actor: str = "human",
    ):
        self.log(AuditEvent(
            event_type=AuditEventType.HITL_DECISION,
            actor=actor,
            skill=skill,
            action=decision,
            detail={"reason": reason},
            session_id=session_id,
        ))

    def log_pipeline_run(
        self,
        pipeline_name: str,
        status: str,
        steps_completed: int,
        total_steps: int,
        duration_ms: float = 0.0,
        errors: list[str] | None = None,
    ):
        self.log(AuditEvent(
            event_type=AuditEventType.PIPELINE_RUN,
            action="run",
            skill=pipeline_name,
            detail={
                "steps_completed": steps_completed,
                "total_steps": total_steps,
                "errors": (errors or [])[:5],
            },
            outcome=status,
            duration_ms=duration_ms,
        ))

    def log_data_access(self, dataset_id: str, actor: str = "system"):
        self.log(AuditEvent(
            event_type=AuditEventType.DATA_ACCESS,
            actor=actor,
            action="load",
            detail={"dataset_id": dataset_id},
        ))

    def query(
        self,
        event_type: AuditEventType | None = None,
        skill: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log entries with optional filters."""
        results = []
        for path in sorted(self._dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        if event_type and entry.get("event_type") != event_type.value:
                            continue
                        if skill and entry.get("skill") != skill:
                            continue
                        if actor and entry.get("actor") != actor:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except (json.JSONDecodeError, IOError):
                continue
        return results

    def summary(self) -> dict[str, Any]:
        """Get audit log summary statistics."""
        entries = self.query(limit=10000)
        by_type: dict[str, int] = {}
        by_skill: dict[str, int] = {}
        by_outcome: dict[str, int] = {}

        for e in entries:
            t = e.get("event_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            s = e.get("skill", "")
            if s:
                by_skill[s] = by_skill.get(s, 0) + 1
            o = e.get("outcome", "unknown")
            by_outcome[o] = by_outcome.get(o, 0) + 1

        return {
            "total_entries": len(entries),
            "by_type": by_type,
            "by_skill": dict(sorted(by_skill.items(), key=lambda x: -x[1])[:10]),
            "by_outcome": by_outcome,
        }


# Module-level singleton
_audit_logger: AuditLogger | None = None


def get_audit_logger(audit_dir: str | None = None) -> AuditLogger:
    """Get or create the singleton audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(audit_dir)
    return _audit_logger
