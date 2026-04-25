"""
HITL (Human-in-the-Loop) Engine — three-level approval system.

Levels:
  - auto: Execute automatically, log decision
  - review: Generate suggestion, wait for confirm/adjust/skip
  - collaborate: Multi-option comparison, human picks
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Literal, Optional

logger = logging.getLogger(__name__)


class HITLDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ADJUSTED = "adjusted"
    SKIPPED = "skipped"
    TIMEOUT_AUTO_APPROVE = "timeout_auto_approve"


@dataclass
class HITLSession:
    """A single HITL approval session."""

    id: str = ""
    level: Literal["auto", "review", "collaborate"] = "auto"
    skill: str = ""
    step_name: str = ""
    status: HITLDecision = HITLDecision.PENDING
    created_at: str = ""
    resolved_at: str = ""
    timeout_seconds: float = 0.0

    # Content presented to human
    title: str = ""
    summary: str = ""
    detail_data: dict = field(default_factory=dict)

    # Available actions
    allowed_actions: list[str] = field(default_factory=list)
    # e.g., ["approve", "reject", "adjust", "skip"]

    # Resolution
    resolution: str = ""  # Human's comment/reasoning
    adjusted_data: dict | None = None

    # Escalation conditions that were triggered
    escalate_triggers: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"hitl_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def is_pending(self) -> bool:
        return self.status == HITLDecision.PENDING

    @property
    def is_timed_out(self) -> bool:
        if not self.timeout_seconds or not self.is_pending:
            return False
        try:
            created = datetime.fromisoformat(self.created_at)
            return datetime.now() > created + timedelta(seconds=self.timeout_seconds)
        except (ValueError, TypeError):
            return False


@dataclass
class ConfidenceResult:
    """Confidence assessment for a decision."""

    score: float  # 0.0 to 1.0
    factors: dict = field(default_factory=dict)
    recommendation: str = ""


class HTLEngine:
    """Core HITL engine managing approval sessions."""

    def __init__(self, default_timeout: float = 1800):  # 30 min default
        self.default_timeout = default_timeout
        self._sessions: dict[str, HITLSession] = {}
        self._decision_callbacks: list[Callable] = []

    def create_session(
        self,
        level: Literal["auto", "review", "collaborate"],
        skill: str,
        step_name: str,
        title: str = "",
        summary: str = "",
        detail_data: dict | None = None,
        allowed_actions: list[str] | None = None,
        timeout: float | None = None,
        escalate_triggers: list[str] | None = None,
    ) -> HITLSession:
        """Create a new HITL session."""
        if allowed_actions is None:
            allowed_actions = ["approve", "reject"]
            if level == "review":
                allowed_actions = ["approve", "adjust", "skip"]
            elif level == "collaborate":
                allowed_actions = ["approve", "reject", "adjust"]

        session = HITLSession(
            level=level,
            skill=skill,
            step_name=step_name,
            title=title or f"{skill} — {level} approval",
            summary=summary,
            detail_data=detail_data or {},
            allowed_actions=allowed_actions,
            timeout_seconds=timeout or self.default_timeout,
            escalate_triggers=escalate_triggers or [],
        )

        self._sessions[session.id] = session
        logger.info(f"HITL session created: {session.id} (level={level}, skill={skill})")

        # Auto-resolve 'auto' level immediately
        if level == "auto":
            self.resolve(session.id, HITLDecision.APPROVED, "Auto-approved")

        return session

    def resolve(
        self,
        session_id: str,
        decision: HITLDecision | str,
        reason: str = "",
        adjusted_data: dict | None = None,
    ) -> HITLSession:
        """Resolve a pending HITL session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Unknown session: {session_id}")

        if not session.is_pending:
            logger.warning(f"Session {session_id} already resolved as {session.status}")
            return session

        if isinstance(decision, str):
            decision = HITLDecision(decision)

        session.status = decision
        session.resolved_at = datetime.now().isoformat()
        session.resolution = reason
        session.adjusted_data = adjusted_data

        logger.info(
            f"HITL session {session_id} resolved: {decision.value} — {reason}"
        )

        # Notify callbacks
        for cb in self._decision_callbacks:
            try:
                cb(session)
            except Exception:
                pass

        return session

    def get_session(self, session_id: str) -> HITLSession | None:
        return self._sessions.get(session_id)

    def get_pending_sessions(self) -> list[HITLSession]:
        return [s for s in self._sessions.values() if s.is_pending]

    def check_timeouts(self) -> list[HITLSession]:
        """Check and auto-approve any timed-out sessions."""
        timed_out = []
        for session in list(self._sessions.values()):
            if session.is_timed_out and session.level != "auto":
                self.resolve(
                    session.id,
                    HITLDecision.TIMEOUT_AUTO_APPROVE,
                    f"Auto-approved after {session.timeout_seconds}s timeout",
                )
                timed_out.append(session)
        return timed_out

    def on_decision(self, callback: Callable[[HITLSession], None]):
        """Register a callback for when decisions are made."""
        self._decision_callbacks.append(callback)

    @property
    def stats(self) -> dict:
        sessions = list(self._sessions.values())
        return {
            "total_sessions": len(sessions),
            "pending": sum(1 for s in sessions if s.is_pending),
            "approved": sum(1 for s in sessions if s.status == HITLDecision.APPROVED),
            "rejected": sum(1 for s in sessions if s.status == HITLDecision.REJECTED),
            "adjusted": sum(1 for s in sessions if s.status == HITLDecision.ADJUSTED),
        }
