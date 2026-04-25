"""
SupplyMind Dashboard — lightweight web server for visualization and HITL UI.

Provides:
- Real-time pipeline execution progress (SSE)
- Data quality dashboard
- Forecast visualization
- Reorder suggestions table
- HITL approval interface

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

        # API routes
        if parsed.path == "/api/status":
            self._send_json(_pipeline_status)
            return
        elif parsed.path == "/api/events":
            self._handle_sse()
            return
        elif parsed.path == "/api/skills":
            self._send_json({"skills": _get_registered_skills()})
            return
        elif parsed.path == "/" or parsed.path == "/index.html":
            self._serve_index()
            return

        # Default: serve static files
        super().do_GET()

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

        # Keep connection alive (in production, use proper event loop)
        try:
            import time
            for i in range(60):  # Keep alive for ~60 seconds
                time.sleep(1)
                # Send heartbeat
                self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except BrokenPipeError:
            pass

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
        skills.append({
            "name": name,
            "description": f"Skill: {name}",
        })
    # Also add known built-in skills
    known_skills = [
        {"name": "data-profiler", "description": "数据质量分析"},
        {"name": "demand-forecast", "description": "需求预测"},
        {"name": "demand-anomaly", "description": "异常检测"},
        {"name": "inventory-classify", "description": "ABC-XYZ 分类"},
        {"name": "inventory-safety-stock", "description": "安全库存计算"},
        {"name": "inventory-reorder", "description": "补货建议"},
        {"name": "report-generator", "description": "报告生成"},
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
    print(f"\n🌐 SupplyMind Dashboard: http://{host:{port}}\n")
    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = start_dashboard(port=8080)
    input("Press Enter to stop...\n")
    server.shutdown()
