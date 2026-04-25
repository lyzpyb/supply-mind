"""
SupplyMind Dashboard — lightweight web server for visualization and HITL UI.

Provides:
- Real-time pipeline execution progress (SSE)
- Data quality dashboard
- Forecast visualization
- Reorder suggestions table
- HITL approval interface (Phase 2: enhanced)
- Memory Insights API
- Decision History API
- Pending Approvals API

Uses Python's built-in http.server for zero-dependency serving.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# ── Module-level singletons ──

_hitl_engine = None
_feedback_collector = None
_learning_loop = None
_skill_evolution = None


def _get_hitl_engine():
    global _hitl_engine, _feedback_collector, _learning_loop
    if _hitl_engine is None:
        _feedback_collector = _get_feedback_collector()
        _learning_loop = _get_learning_loop()
        from supplymind.hitl.engine import HTLEngine
        _hitl_engine = HTLEngine(
            feedback_collector=_feedback_collector,
            learning_loop=_learning_loop,
        )
    return _hitl_engine


def _get_feedback_collector():
    global _feedback_collector
    if _feedback_collector is None:
        from supplymind.hitl.feedback import FeedbackCollector
        _feedback_collector = FeedbackCollector()
    return _feedback_collector


def _get_learning_loop():
    global _learning_loop
    if _learning_loop is None:
        try:
            from supplymind.learning.loop import LearningLoop
            from supplymind.memory.domain import DomainMemory
            dm = DomainMemory()
            _learning_loop = LearningLoop(domain_memory=dm)
        except Exception:
            from supplymind.learning.loop import LearningLoop
            _learning_loop = LearningLoop()
    return _learning_loop


def _get_skill_evolution():
    global _skill_evolution
    if _skill_evolution is None:
        from supplymind.learning.evolution import SkillEvolution
        _skill_evolution = SkillEvolution()
    return _skill_evolution

# Global SSE event queue for real-time updates
_sse_subscribers: list[Callable] = []
_pipeline_status: dict = {
    "running": False,
    "current_step": "",
    "progress": 0,
    "steps_completed": 0,
    "total_steps": 0,
    "message": "Ready",
}


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with API routes and SSE support."""

    def __init__(self, *args, **kwargs):
        self.static_dir = Path(__file__).parent / "static"
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        # ── Core APIs ──
        if parsed.path == "/api/status":
            self._send_json(_pipeline_status)
            return
        elif parsed.path == "/api/events":
            self._handle_sse()
            return
        elif parsed.path == "/api/skills":
            self._send_json({"skills": _get_registered_skills()})
            return

        # ── Phase 2 Enhanced APIs ──
        elif parsed.path == "/api/memory/insights":
            self._send_json(self._get_memory_insights())
            return
        elif parsed.path == "/api/memory/domain":
            self._send_json(self._get_domain_memory())
            return
        elif parsed.path == "/api/memory/meta":
            self._send_json(self._get_meta_memory())
            return
        elif parsed.path == "/api/decisions/history":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            self._send_json(self._get_decision_history(limit))
            return
        elif parsed.path == "/api/hitl/pending":
            self._send_json(self._get_pending_approvals())
            return
        elif parsed.path == "/api/hitl/approve":
            # GET to list pending, POST to approve
            self._send_json(self._get_pending_approvals())
            return
        elif parsed.path == "/api/feedback/summary":
            self._send_json(self._get_feedback_summary())
            return
        elif parsed.path == "/api/evolution/profiles":
            self._send_json(self._get_evolution_profiles())
            return

        # Serve static files or index
        elif parsed.path == "/" or parsed.path == "/index.html":
            self._serve_index()
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if parsed.path == "/api/hitl/approve":
            result = self._handle_hitl_approve(data)
            self._send_json(result)
            return
        elif parsed.path == "/api/hitl/reject":
            result = self._handle_hitl_reject(data)
            self._send_json(result)
            return
        elif parsed.path == "/api/hitl/adjust":
            result = self._handle_hitl_adjust(data)
            self._send_json(result)
            return
        elif parsed.path == "/api/feedback/record":
            result = self._handle_record_feedback(data)
            self._send_json(result)
            return

        self.send_response(404)
        self._send_json({"error": f"Unknown endpoint: {parsed.path}"})

    def _serve_index(self):
        """Serve the main dashboard HTML."""
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404, "Dashboard not found")

    def _handle_sse(self):
        """Handle Server-Sent Events connection."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial status
        self.wfile.write(f"data: {json.dumps(_pipeline_status)}\n\n".encode())
        self.wfile.flush()

        try:
            import time
            for i in range(120):  # Keep alive for ~2 minutes
                time.sleep(1)
                self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except BrokenPipeError:
            pass

    # ── Phase 2: Memory APIs ──

    @staticmethod
    def _get_memory_insights() -> dict:
        """Get aggregated memory insights across all layers."""
        try:
            from supplymind.memory import MemoryManager
            mm = MemoryManager()
            return mm.get_memory_insights()
        except Exception as e:
            return {"error": str(e), "layers_available": False}

    @staticmethod
    def _get_domain_memory() -> dict:
        """Get domain memory contents."""
        try:
            from supplymind.memory.domain import DomainMemory
            dm = DomainMemory()
            return {
                "summary": dm.summary(),
                "data_profile": dm._data.get("data_profile", {}),
                "preferences": dm._data.get("parameter_prefs", {}),
                "model_performance_categories": list(dm._data.get("model_performance", {}).keys()),
                "pattern_count": len(dm._data.get("anomaly_patterns", [])),
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _get_meta_memory() -> dict:
        """Get meta memory contents."""
        try:
            from supplymind.memory.meta import MetaMemory
            mm = MetaMemory()
            return mm.get_all()
        except Exception as e:
            return {"error": str(e)}

    # ── Phase 2: Decision History API ──

    @staticmethod
    def _get_decision_history(limit: int = 20) -> dict:
        """Get recent decision history."""
        try:
            from supplymind.memory.meta import MetaMemory
            mm = MetaMemory()
            decisions = mm.get_recent_decisions(limit)
            return {
                "decisions": decisions,
                "total": len(mm._data.get("decision_history", [])),
                "limit": limit,
            }
        except Exception as e:
            return {"error": str(e), "decisions": [], "total": 0}

    # ── Phase 2: HITL Approval APIs ──

    @staticmethod
    def _get_pending_approvals() -> dict:
        """Get pending HITL approvals."""
        try:
            engine = _get_hitl_engine()
            pending = engine.get_pending_sessions()
            return {
                "pending": [
                    {
                        "id": s.id,
                        "level": s.level,
                        "skill": s.skill,
                        "step_name": s.step_name,
                        "title": s.title,
                        "summary": s.summary,
                        "created_at": s.created_at,
                        "allowed_actions": s.allowed_actions,
                    }
                    for s in pending
                ],
                "count": len(pending),
            }
        except Exception as e:
            return {"error": str(e), "pending": [], "count": 0}

    @staticmethod
    def _handle_hitl_approve(data: dict) -> dict:
        """Approve a pending HITL session."""
        try:
            from supplymind.hitl.engine import HITLDecision
            from supplymind.memory.meta import MetaMemory

            session_id = data.get("session_id", "")
            reason = data.get("reason", "Approved via Dashboard")

            engine = _get_hitl_engine()
            session = engine.resolve(session_id, HITLDecision.APPROVED, reason)

            # Record in meta memory
            mm = MetaMemory()
            mm.record_decision(
                decision_id=session_id,
                skill=session.skill,
                decision_type="approved",
                confidence=0.9,
                summary=session.summary[:200] if session.summary else "",
            )

            return {"success": True, "session_id": session_id, "status": "approved"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _handle_hitl_reject(data: dict) -> dict:
        """Reject a pending HITL session."""
        try:
            from supplymind.hitl.engine import HITLDecision
            from supplymind.memory.meta import MetaMemory

            session_id = data.get("session_id", "")
            reason = data.get("reason", "Rejected via Dashboard")

            engine = _get_hitl_engine()
            session = engine.resolve(session_id, HITLDecision.REJECTED, reason)

            mm = MetaMemory()
            mm.record_decision(
                decision_id=session_id,
                skill=session.skill,
                decision_type="rejected",
                confidence=0.9,
                summary=session.summary[:200] if session.summary else "",
            )

            return {"success": True, "session_id": session_id, "status": "rejected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _handle_hitl_adjust(data: dict) -> dict:
        """Adjust a pending HITL session with modified values."""
        try:
            from supplymind.hitl.engine import HITLDecision
            from supplymind.memory.meta import MetaMemory

            session_id = data.get("session_id", "")
            reason = data.get("reason", "Adjusted via Dashboard")
            adjusted_data = data.get("adjusted_data", {})

            engine = _get_hitl_engine()
            session = engine.resolve(session_id, HITLDecision.ADJUSTED, reason, adjusted_data)

            # Record feedback via shared collector
            fc = _get_feedback_collector()
            from supplymind.hitl.feedback import FeedbackType
            fc.record(
                session_id=session_id,
                feedback_type=FeedbackType.IMPLICIT_ADJUST,
                skill=session.skill,
                original=session.detail_data,
                adjustment=adjusted_data,
                comment=reason,
                hitl_session_id=session_id,
                original_value=data.get("original_value"),
                adjusted_value=data.get("adjusted_value"),
                sku_id=data.get("sku_id", ""),
                category=data.get("category", ""),
            )

            mm = MetaMemory()
            mm.record_decision(
                decision_id=session_id,
                skill=session.skill,
                decision_type="adjusted",
                confidence=0.85,
                summary=f"Adjusted: {reason}",
            )

            return {"success": True, "session_id": session_id, "status": "adjusted"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Phase 2: Feedback API ──

    @staticmethod
    def _get_feedback_summary() -> dict:
        """Get feedback summary statistics."""
        try:
            fc = _get_feedback_collector()
            return fc.summary()
        except Exception as e:
            return {"error": str(e), "total_feedbacks": 0}

    @staticmethod
    def _handle_record_feedback(data: dict) -> dict:
        """Record a new feedback entry."""
        try:
            from supplymind.hitl.feedback import FeedbackType

            fc = _get_feedback_collector()
            fc.record(
                session_id=data.get("session_id", ""),
                feedback_type=data.get("type", "implicit_adopt"),
                skill=data.get("skill", ""),
                original=data.get("original"),
                adjustment=data.get("adjustment"),
                comment=data.get("comment", ""),
                sku_id=data.get("sku_id", ""),
                category=data.get("category", ""),
                hitl_session_id=data.get("hitl_session_id", ""),
                original_value=data.get("original_value"),
                adjusted_value=data.get("adjusted_value"),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _get_evolution_profiles() -> dict:
        """Get evolution profile summaries."""
        try:
            se = _get_skill_evolution()

            profiles = []
            for path in se.storage_dir.glob("*_evolution.json"):
                name = path.stem.replace("_evolution", "")
                profile = se.get_profile(name)
                profiles.append(se.get_evolution_summary(name))

            return {"profiles": profiles}
        except Exception as e:
            return {"error": str(e), "profiles": []}

    # ── Utilities ──

    def _send_json(self, data: dict):
        """Send JSON response."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Override to reduce noise."""
        logger.debug(f"Dashboard HTTP: {format % args}")


def _get_registered_skills() -> list[dict]:
    """Get list of registered skills for the dashboard."""
    from supplymind.pipelines.engine import SKILL_REGISTRY
    skills = []
    for name in SKILL_REGISTRY:
        skills.append({"name": name, "description": f"Skill: {name}"})

    known_skills = [
        {"name": "data-profiler", "description": "Data Quality Profiler"},
        {"name": "demand-forecast", "description": "Demand Forecasting"},
        {"name": "demand-anomaly", "description": "Anomaly Detection"},
        {"name": "demand-decompose", "description": "Time Series Decomposition"},
        {"name": "demand-newproduct", "description": "New Product Cold-Start"},
        {"name": "demand-intermittent", "description": "Intermittent Demand (Croston)"},
        {"name": "demand-reconcile", "description": "Multi-Level Demand Reconciliation"},
        {"name": "inventory-classify", "description": "ABC-XYZ Classification"},
        {"name": "inventory-safety-stock", "description": "Safety Stock Calculation"},
        {"name": "inventory-reorder", "description": "Reorder Suggestions"},
        {"name": "inventory-policy-sim", "description": "Policy Simulation (Monte Carlo)"},
        {"name": "inventory-multi-echelon", "description": "Multi-Echelon Optimization"},
        {"name": "inventory-newsvendor", "description": "Newsvendor Model"},
        {"name": "report-generator", "description": "Report Generation"},
    ]
    seen = {s["name"] for s in skills}
    for s in known_skills:
        if s["name"] not in seen:
            skills.append(s)
    return skills


def update_pipeline_status(**kwargs):
    """Update global pipeline status (called by PipelineEngine)."""
    global _pipeline_status
    _pipeline_status.update(kwargs)


def start_dashboard(host: str = "127.0.0.1", port: int = 8080) -> HTTPServer:
    """Start the Dashboard web server.

    Args:
        host: Bind address
        port: Port number

    Returns:
        The running HTTPServer instance
    """
    server = HTTPServer((host, port), DashboardRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Dashboard started at http://{host}:{port}")
    print(f"\n  SupplyMind Dashboard: http://{host}:{port}\n")
    print(f"  APIs:")
    print(f"    - GET  /api/skills              List all available Skills")
    print(f"    - GET  /api/status               Pipeline status")
    print(f"    - GET  /api/events               SSE real-time events")
    print(f"    - GET  /api/memory/insights      Memory system overview")
    print(f"    - GET  /api/memory/domain        Domain memory details")
    print(f"    - GET  /api/memory/meta           Meta memory details")
    print(f"    - GET  /api/decisions/history     Recent decision history")
    print(f"    - GET  /api/hitl/pending          Pending approvals")
    print(f"    - POST /api/hitl/approve          Approve a decision")
    print(f"    - POST /api/hitl/reject           Reject a decision")
    print(f"    - POST /api/hitl/adjust           Adjust a decision")
    print(f"    - GET  /api/feedback/summary       Feedback statistics")
    print(f"    - GET  /api/evolution/profiles    Skill evolution profiles\n")
    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = start_dashboard(port=8080)
    input("Press Enter to stop...\n")
    server.shutdown()
