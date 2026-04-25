"""
Multi-Agent Orchestrator — decomposes complex supply chain questions
into sub-tasks and delegates to specialized skill agents.

Pattern: Orchestrator → [Research Agent, Forecast Agent, Inventory Agent, ...] → Synthesis

This is a lightweight, LLM-free orchestrator that uses rule-based task
decomposition. For LLM-driven orchestration, pair with the ToolRouter
and an LLM client (OpenAI, Anthropic, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """A sub-task delegated to a skill agent."""
    id: str
    skill: str
    description: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    result: str | None = None
    success: bool = False
    duration_ms: float = 0.0


@dataclass
class OrchestrationPlan:
    """Execution plan produced by the orchestrator."""
    query: str
    tasks: list[SubTask] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Result of a multi-agent orchestration run."""
    query: str
    plan: OrchestrationPlan
    task_results: dict[str, SubTask] = field(default_factory=dict)
    synthesis: str = ""
    total_duration_ms: float = 0.0
    success: bool = False


# Task decomposition patterns
_PATTERNS: list[dict[str, Any]] = [
    {
        "keywords": ["补货", "replenish", "reorder", "进货", "备货"],
        "tasks": [
            {"skill": "data_profiler", "desc": "Profile input data quality"},
            {"skill": "demand_anomaly", "desc": "Detect and clean anomalies"},
            {"skill": "demand_forecast", "desc": "Generate demand forecasts"},
            {"skill": "inventory_classify", "desc": "Classify SKUs by ABC-XYZ"},
            {"skill": "inventory_safety_stock", "desc": "Calculate safety stock"},
            {"skill": "inventory_reorder", "desc": "Generate reorder suggestions"},
        ],
        "deps": {
            "demand_anomaly": ["data_profiler"],
            "demand_forecast": ["demand_anomaly"],
            "inventory_classify": ["demand_forecast"],
            "inventory_safety_stock": ["inventory_classify"],
            "inventory_reorder": ["inventory_safety_stock"],
        },
    },
    {
        "keywords": ["定价", "pricing", "价格", "markdown", "clearance"],
        "tasks": [
            {"skill": "pricing_elasticity", "desc": "Estimate price elasticity"},
            {"skill": "pricing_lifecycle", "desc": "Detect product lifecycle stage"},
            {"skill": "pricing_markdown", "desc": "Optimize markdown pricing"},
            {"skill": "pricing_bundling", "desc": "Recommend product bundles"},
        ],
        "deps": {
            "pricing_markdown": ["pricing_elasticity"],
        },
    },
    {
        "keywords": ["预测", "forecast", "需求"],
        "tasks": [
            {"skill": "data_profiler", "desc": "Profile data quality"},
            {"skill": "demand_decompose", "desc": "Decompose time series"},
            {"skill": "demand_forecast", "desc": "Generate forecasts"},
        ],
        "deps": {
            "demand_decompose": ["data_profiler"],
            "demand_forecast": ["data_profiler"],
        },
    },
    {
        "keywords": ["配送", "fulfillment", "routing", "delivery", "物流"],
        "tasks": [
            {"skill": "fulfill_allocation", "desc": "Allocate inventory"},
            {"skill": "fulfill_routing", "desc": "Optimize delivery routes"},
            {"skill": "fulfill_wave", "desc": "Plan wave picking"},
            {"skill": "fulfill_capacity", "desc": "Check capacity"},
        ],
        "deps": {},
    },
]


class Orchestrator:
    """Multi-agent orchestrator for complex supply chain queries."""

    def __init__(self, router=None):
        """
        Args:
            router: ToolRouter instance. If None, creates one with all skills.
        """
        self._router = router

    def _get_router(self):
        if self._router is None:
            from supplymind.agent.tools import get_tool_router
            self._router = get_tool_router()
        return self._router

    def plan(self, query: str, context: dict[str, Any] | None = None) -> OrchestrationPlan:
        """Decompose a query into an execution plan."""
        query_lower = query.lower()
        matched_pattern = None

        for pattern in _PATTERNS:
            if any(kw in query_lower for kw in pattern["keywords"]):
                matched_pattern = pattern
                break

        if not matched_pattern:
            return OrchestrationPlan(
                query=query,
                tasks=[SubTask(id="fallback", skill="data_profiler",
                               description="No specific pattern matched; profiling data")],
                execution_order=[["fallback"]],
            )

        tasks = []
        for t in matched_pattern["tasks"]:
            task = SubTask(
                id=t["skill"],
                skill=t["skill"],
                description=t["desc"],
                arguments=context or {},
                depends_on=matched_pattern.get("deps", {}).get(t["skill"], []),
            )
            tasks.append(task)

        execution_order = self._topological_sort(tasks)

        return OrchestrationPlan(
            query=query,
            tasks=tasks,
            execution_order=execution_order,
        )

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Plan and execute a multi-agent orchestration."""
        t0 = time.time()
        plan = self.plan(query, context)
        router = self._get_router()

        task_map = {t.id: t for t in plan.tasks}
        results: dict[str, SubTask] = {}

        for wave in plan.execution_order:
            coros = []
            for task_id in wave:
                task = task_map[task_id]
                task.status = "running"
                coros.append(self._execute_task(router, task))

            wave_results = await asyncio.gather(*coros, return_exceptions=True)

            for task_id, result in zip(wave, wave_results):
                task = task_map[task_id]
                if isinstance(result, Exception):
                    task.status = "failed"
                    task.result = str(result)
                    task.success = False
                else:
                    task.status = "completed"
                    task.result = result[0]
                    task.success = result[1]
                results[task_id] = task

        synthesis = self._synthesize(query, results)
        elapsed = (time.time() - t0) * 1000

        all_success = all(t.success for t in results.values())

        return OrchestrationResult(
            query=query,
            plan=plan,
            task_results=results,
            synthesis=synthesis,
            total_duration_ms=elapsed,
            success=all_success,
        )

    async def _execute_task(self, router, task: SubTask) -> tuple[str, bool]:
        t0 = time.time()
        result = await router.call_tool(task.skill, task.arguments)
        task.duration_ms = (time.time() - t0) * 1000
        return result

    def _synthesize(self, query: str, results: dict[str, SubTask]) -> str:
        """Synthesize results from all sub-tasks into a summary."""
        lines = [f"# Orchestration Results for: {query}", ""]

        completed = [t for t in results.values() if t.success]
        failed = [t for t in results.values() if not t.success]

        lines.append(f"Completed: {len(completed)}/{len(results)} tasks")
        if failed:
            lines.append(f"Failed: {', '.join(t.skill for t in failed)}")
        lines.append("")

        for task in results.values():
            status = "OK" if task.success else "FAILED"
            lines.append(f"## [{status}] {task.skill} ({task.duration_ms:.0f}ms)")
            lines.append(f"{task.description}")
            if task.result:
                preview = task.result[:500]
                if len(task.result) > 500:
                    preview += "..."
                lines.append(f"\n{preview}\n")

        return "\n".join(lines)

    def _topological_sort(self, tasks: list[SubTask]) -> list[list[str]]:
        """Sort tasks into execution waves respecting dependencies."""
        task_ids = {t.id for t in tasks}
        deps = {t.id: [d for d in t.depends_on if d in task_ids] for t in tasks}
        resolved: set[str] = set()
        waves: list[list[str]] = []

        remaining = set(task_ids)
        while remaining:
            wave = [tid for tid in remaining if all(d in resolved for d in deps[tid])]
            if not wave:
                wave = list(remaining)
            waves.append(wave)
            resolved.update(wave)
            remaining -= set(wave)

        return waves
