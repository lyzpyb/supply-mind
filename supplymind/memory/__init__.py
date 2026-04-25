"""
SupplyMind Memory System — unified memory management.

Four-layer architecture:
  1. Working Memory — session-scoped, ephemeral (per pipeline run)
  2. Domain Memory — project-scoped, persistent (per project data profiles)
  3. Meta Memory — agent-level, permanent (cross-project learnings & styles)
  4. Evolution Memory — skill evolution tracking (performance over time)
"""

from supplymind.memory.working import WorkingMemory
from supplymind.memory.domain import DomainMemory
from supplymind.memory.meta import MetaMemory
from supplymind.memory.store import JSONFileStore


class MemoryManager:
    """Unified interface to all memory layers.

    Provides a single point of access for reading/writing across
    working, domain, meta, and evolution memories.
    """

    def __init__(self, project_id: str = "default"):
        self.working = WorkingMemory()
        self.domain = DomainMemory(project_id=project_id)
        self.meta = MetaMemory()
        self.evolution_store = JSONFileStore(base_dir=".supplymind/evolution")

    def initialize_session(self, pipeline_name: str = ""):
        """Initialize working memory for a new session."""
        self.working.clear()
        self.working.set("_session_pipeline", pipeline_name)
        self.working.set("_session_start", __import__("datetime").datetime.now().isoformat())

    def get_memory_insights(self) -> dict:
        """Get aggregated insights across all memory layers for Dashboard."""
        from supplymind.learning.evolution import SkillEvolution

        evolution = SkillEvolution()

        return {
            "working": {
                "session_id": self.working.session_id,
                "items": self.working.size,
            },
            "domain": self.domain.summary(),
            "meta": self.meta.summary(),
            "evolution": {
                "profiles_available": sum(1 for _ in evolution.storage_dir.glob("*_evolution.json")) if evolution.storage_dir.exists() else 0,
            },
        }

    def export_state(self) -> dict:
        """Export current state of all memory layers (for debugging)."""
        return {
            "working_keys": self.working.keys(),
            "domain_summary": self.domain.summary(),
            "meta_summary": self.meta.summary(),
        }
