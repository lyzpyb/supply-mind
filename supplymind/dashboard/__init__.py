"""SupplyMind Dashboard — web UI for pipeline visualization and HITL."""

from supplymind.dashboard.server import (
    DashboardRequestHandler,
    start_dashboard,
    update_pipeline_status,
    _get_registered_skills,
)

__all__ = [
    "DashboardRequestHandler",
    "start_dashboard",
    "update_pipeline_status",
    "_get_registered_skills",
]
