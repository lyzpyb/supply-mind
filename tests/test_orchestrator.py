"""Tests for multi-agent orchestrator."""

import asyncio

import pytest

from supplymind.agent.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    OrchestrationResult,
    SubTask,
)


class TestOrchestrationPlanning:
    """Test query decomposition into execution plans."""

    def test_replenish_query_decomposition(self):
        orch = Orchestrator()
        plan = orch.plan("帮我做一下补货分析")
        assert len(plan.tasks) >= 4
        skills = {t.skill for t in plan.tasks}
        assert "demand_forecast" in skills
        assert "inventory_reorder" in skills

    def test_pricing_query_decomposition(self):
        orch = Orchestrator()
        plan = orch.plan("optimize pricing strategy for clearance")
        skills = {t.skill for t in plan.tasks}
        assert "pricing_elasticity" in skills
        assert "pricing_markdown" in skills

    def test_forecast_query_decomposition(self):
        orch = Orchestrator()
        plan = orch.plan("需求预测分析")
        skills = {t.skill for t in plan.tasks}
        assert "demand_forecast" in skills

    def test_fulfillment_query_decomposition(self):
        orch = Orchestrator()
        plan = orch.plan("optimize delivery routing")
        skills = {t.skill for t in plan.tasks}
        assert "fulfill_routing" in skills

    def test_unknown_query_fallback(self):
        orch = Orchestrator()
        plan = orch.plan("something completely unrelated xyz123")
        assert len(plan.tasks) == 1
        assert plan.tasks[0].skill == "data_profiler"

    def test_execution_order_respects_deps(self):
        orch = Orchestrator()
        plan = orch.plan("replenishment analysis")

        flat_order = []
        for wave in plan.execution_order:
            flat_order.extend(wave)

        for task in plan.tasks:
            if task.depends_on:
                task_idx = flat_order.index(task.id)
                for dep in task.depends_on:
                    if dep in flat_order:
                        dep_idx = flat_order.index(dep)
                        assert dep_idx < task_idx, f"{dep} should come before {task.id}"


class TestTopologicalSort:
    """Test dependency resolution."""

    def test_no_deps_single_wave(self):
        orch = Orchestrator()
        tasks = [
            SubTask(id="a", skill="a", description=""),
            SubTask(id="b", skill="b", description=""),
        ]
        waves = orch._topological_sort(tasks)
        assert len(waves) == 1
        assert set(waves[0]) == {"a", "b"}

    def test_linear_deps(self):
        orch = Orchestrator()
        tasks = [
            SubTask(id="a", skill="a", description=""),
            SubTask(id="b", skill="b", description="", depends_on=["a"]),
            SubTask(id="c", skill="c", description="", depends_on=["b"]),
        ]
        waves = orch._topological_sort(tasks)
        assert len(waves) == 3
        assert waves[0] == ["a"]
        assert waves[1] == ["b"]
        assert waves[2] == ["c"]

    def test_parallel_deps(self):
        orch = Orchestrator()
        tasks = [
            SubTask(id="a", skill="a", description=""),
            SubTask(id="b", skill="b", description="", depends_on=["a"]),
            SubTask(id="c", skill="c", description="", depends_on=["a"]),
        ]
        waves = orch._topological_sort(tasks)
        assert waves[0] == ["a"]
        assert set(waves[1]) == {"b", "c"}


class TestOrchestrationExecution:
    """Test actual orchestration execution."""

    def test_execute_simple_plan(self):
        orch = Orchestrator()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orch.execute("需求预测", context={"demand_history": [
                    {"sku_id": "SKU001", "date": f"2026-01-{d:02d}", "quantity": 100 + d}
                    for d in range(1, 31)
                ]})
            )
        finally:
            loop.close()

        assert isinstance(result, OrchestrationResult)
        assert result.total_duration_ms > 0
        assert len(result.task_results) > 0
        assert result.synthesis != ""

    def test_synthesis_contains_task_summaries(self):
        orch = Orchestrator()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orch.execute("forecast demand", context={"demand_history": [
                    {"sku_id": "SKU001", "date": f"2026-01-{d:02d}", "quantity": 50 + d * 2}
                    for d in range(1, 31)
                ]})
            )
        finally:
            loop.close()

        assert "Orchestration Results" in result.synthesis
        assert "demand_forecast" in result.synthesis
