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

    def __init__(
        self,
        default_timeout: float = 1800,
        feedback_collector=None,
        learning_loop=None,
        store=None,
    ):
        self.default_timeout = default_timeout
        self._sessions: dict[str, HITLSession] = {}
        self._decision_callbacks: list[Callable] = []
        self._feedback_collector = feedback_collector
        self._learning_loop = learning_loop
        self._store = store

        if feedback_collector and learning_loop:
            feedback_collector.set_learning_callback(learning_loop.on_feedback)

        if store:
            self._restore_sessions()

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
        self._persist_session(session)

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
        self._persist_session(session)

        # Notify callbacks
        for cb in self._decision_callbacks:
            try:
                cb(session)
            except Exception:
                pass

        # Feed into learning loop via feedback collector
        if self._feedback_collector and decision in (
            HITLDecision.ADJUSTED, HITLDecision.REJECTED,
        ):
            from supplymind.hitl.feedback import FeedbackType
            fb_type = (
                FeedbackType.IMPLICIT_ADJUST if decision == HITLDecision.ADJUSTED
                else FeedbackType.IMPLICIT_REJECT
            )
            try:
                self._feedback_collector.record(
                    session_id=session_id,
                    feedback_type=fb_type,
                    skill=session.skill,
                    original=session.detail_data,
                    adjustment=adjusted_data,
                    comment=reason,
                    hitl_session_id=session_id,
                )
            except Exception as e:
                logger.debug(f"Feedback recording failed: {e}")

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

    def _persist_session(self, session: HITLSession):
        if not self._store:
            return
        try:
            data = {
                "id": session.id,
                "level": session.level,
                "skill": session.skill,
                "step_name": session.step_name,
                "title": session.title,
                "summary": session.summary,
                "detail_data": session.detail_data,
                "status": session.status.value if isinstance(session.status, HITLDecision) else str(session.status),
                "created_at": session.created_at,
                "resolved_at": session.resolved_at,
                "resolution": session.resolution,
                "adjusted_data": session.adjusted_data,
                "timeout_seconds": session.timeout_seconds,
            }
            self._store.save(session.id, data)
        except Exception as e:
            logger.debug(f"Session persist failed: {e}")

    def _restore_sessions(self):
        if not self._store:
            return
        try:
            all_data = self._store.load_all()
            for sid, data in all_data.items():
                status_str = data.get("status", "pending")
                if status_str == "pending":
                    session = HITLSession(
                        level=data.get("level", "review"),
                        skill=data.get("skill", ""),
                        step_name=data.get("step_name", ""),
                        title=data.get("title", ""),
                        summary=data.get("summary", ""),
                        detail_data=data.get("detail_data", {}),
                        timeout_seconds=data.get("timeout_seconds", self.default_timeout),
                    )
                    session.id = sid
                    session.created_at = data.get("created_at", session.created_at)
                    self._sessions[sid] = session
            logger.info(f"Restored {len(self._sessions)} pending HITL sessions from store")
        except Exception as e:
            logger.warning(f"Session restore failed: {e}")
