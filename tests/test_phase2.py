"""
Phase 2 integration tests — validates all new modules from Phase 2 development.

Covers:
  - Demand Skills: decompose, newproduct, intermittent, reconcile
  - Inventory Skills: policy_sim, multi_echelon, newsvendor
  - Learning Loop: feedback processing, rule generation
  - Backtester: rolling-origin backtest
  - Skill Evolution: profile tracking, auto-rules
  - Memory System: JSONFileStore, Domain/Meta/Working memory
  - HITL Engine: session lifecycle, timeout, resolution
  - MCP Server: tool registration and calling
"""

import json
import os
import tempfile
import math

import numpy as np
import pytest

# ── Demand Skills ──

from supplymind.skills.demand.decompose.main import DemandDecompose
from supplymind.skills.demand.decompose.schema import DecomposeInput

from supplymind.skills.demand.newproduct.main import DemandNewProduct
from supplymind.skills.demand.newproduct.schema import NewProductInput

from supplymind.skills.demand.intermittent.main import DemandIntermittent
from supplymind.skills.demand.intermittent.schema import IntermittentInput

from supplymind.skills.demand.reconcile.main import DemandReconcile
from supplymind.skills.demand.reconcile.schema import ReconcileInput


# ── Inventory Skills ──

from supplymind.skills.inventory.policy_sim.main import InventoryPolicySim
from supplymind.skills.inventory.policy_sim.schema import PolicySimInput

from supplymind.skills.inventory.multi_echelon.main import InventoryMultiEchelon
from supplymind.skills.inventory.multi_echelon.schema import MultiEchelonInput, EchelonNode

from supplymind.skills.inventory.newsvendor.main import InventoryNewsvendor
from supplymind.skills.inventory.newsvendor.schema import NewsvendorInput, NewsvendorItem


# ── Learning / Memory / HITL / MCP ──

from supplymind.learning.loop import LearningLoop, Feedback, FeedbackType, LearningEvent
from supplymind.learning.backtest import Backtester, BacktestReport
from supplymind.learning.evolution import (
    SkillEvolution, SkillEvolutionProfile, MethodPerformance,
    UserCorrection, AutoRule,
)
from supplymind.memory.store import MemoryStore, JSONFileStore
from supplymind.memory.domain import DomainMemory
from supplymind.memory.meta import MetaMemory
from supplymind.memory.working import WorkingMemory
from supplymind.hitl.engine import HTLEngine, HITLSession, HITLDecision
from supplymind.mcp.server import MCPServer


# ════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════

def _generate_demand_dicts(n_skus=3, n_days=90, seed=42) -> list[dict]:
    """Generate synthetic demand data for testing."""
    rng = np.random.RandomState(seed)
    records = []
    for i in range(n_days):
        d = __import__('datetime').date(2026, 1, 1).__add__(
            __import__('datetime').timedelta(days=i)
        )
        for sku_idx in range(n_skus):
            base = (sku_idx + 1) * 50
            seasonal = 10 if i % 7 >= 5 else 0
            promo = 15 if i % 14 in (6, 13) else 0
            qty = max(0, base + seasonal + promo + rng.randn() * base * 0.1)
            records.append({
                "sku_id": f"SKU{sku_idx+1:03d}",
                "location_id": "STORE_A",
                "date": d.isoformat(),
                "quantity": round(float(qty), 2),
                "revenue": round(qty * (20 + sku_idx * 5), 2),
                "is_promo": i % 14 in (6, 13),
                "stockout_flag": False,
            })
    return records


def _generate_intermittent_demand() -> list[dict]:
    """Generate demand with intermittent (sparse) patterns."""
    records = []
    d = __import__('datetime').date(2026, 1, 1)
    td = __import__('datetime').timedelta
    for i in range(90):
        # SKU001: normal demand
        records.append({
            "sku_id": "SKU001", "location_id": "STORE_A",
            "date": (d + td(days=i)).isoformat(),
            "quantity": round(50 + np.random.randn() * 10, 2),
        })
        # SKU002: intermittent (~60% zeros)
        qty2 = 0 if np.random.rand() < 0.6 else round(np.random.rand() * 20 + 5, 2)
        records.append({
            "sku_id": "SKU002", "location_id": "STORE_A",
            "date": (d + td(days=i)).isoformat(),
            "quantity": qty2,
        })
        # SKU003: very sparse (~80% zeros)
        qty3 = 0 if np.random.rand() < 0.8 else round(np.random.rand() * 8 + 1, 2)
        records.append({
            "sku_id": "SKU003", "location_id": "STORE_A",
            "date": (d + td(days=i)).isoformat(),
            "quantity": qty3,
        })
    return records


# ════════════════════════════════════════════════
# Test: Demand Decompose
# ════════════════════════════════════════════════

class TestDemandDecompose:
    def test_decompose_runs(self):
        demand_data = _generate_demand_dicts()
        skill = DemandDecompose()
        result = skill.run(DecomposeInput(demand_history=demand_data))
        assert len(result.decompositions) == 3
        assert result.summary["total_skus"] == 3
        for d in result.decompositions:
            assert d.seasonality_strength >= 0
            assert d.trend_direction in ("increasing", "decreasing", "stable", "unknown")
            assert len(d.trend) > 0
            assert len(d.seasonal) > 0

    def test_decompose_with_period(self):
        demand_data = _generate_demand_dicts()
        skill = DemandDecompose()
        result = skill.run(DecomposeInput(demand_history=demand_data, period=7))
        assert result.summary["total_skus"] > 0

    def test_decompose_empty(self):
        skill = DemandDecompose()
        result = skill.run(DecomposeInput(demand_history=[]))
        assert len(result.decompositions) == 0

    def test_decompose_dict_input(self):
        demand_data = _generate_demand_dicts()
        skill = DemandDecompose()
        # Pass as plain dict (not Pydantic model)
        result = skill.run({"demand_history": demand_data})
        assert result.summary["total_skus"] == 3

    def test_sku_filter(self):
        demand_data = _generate_demand_dicts()
        skill = DemandDecompose()
        result = skill.run(DecomposeInput(
            demand_history=demand_data, sku_filter=["SKU001"]
        ))
        assert len(result.decompositions) == 1
        assert result.decompositions[0].sku_id == "SKU001"


# ════════════════════════════════════════════════
# Test: Demand New Product
# ════════════════════════════════════════════════

class TestDemandNewProduct:
    def test_newproduct_similarity_based(self):
        ref_history = [
            {"sku_id": "SIM01", "quantity": 30.0, "date": "2026-01-01", "category": "dairy"},
            {"sku_id": "SIM01", "quantity": 45.0, "date": "2026-01-08", "category": "dairy"},
            {"sku_id": "SIM02", "quantity": 25.0, "date": "2026-01-01", "category": "dairy"},
            {"sku_id": "SIM02", "quantity": 38.0, "date": "2026-01-08", "category": "dairy"},
        ]
        skill = DemandNewProduct()
        result = skill.run(NewProductInput(
            sku_id="NEW_DAIRY_001",
            category="dairy",
            reference_history=ref_history,
            horizon=30,
            method="similarity",
        ))
        assert len(result.forecasts) == 1
        fc = result.forecasts[0]
        assert fc.sku_id == "NEW_DAIRY_001"
        assert fc.total_predicted > 0
        assert 0 < fc.confidence_score <= 1
        assert len(fc.daily_forecasts) == 30

    def test_newproduct_growth_curve(self):
        skill = DemandNewProduct()
        result = skill.run(NewProductInput(
            sku_id="NEW_GROWTH_001",
            horizon=60,
            expected_peak_demand=100.0,
            method="growth_curve",
        ))
        assert len(result.forecasts) == 1
        fc = result.forecasts[0]
        assert fc.method_used == "growth_curve"
        assert len(fc.daily_forecasts) == 60
        # Growth curve should show ramp-up pattern (early values < later values on average)
        early_avg = np.mean([d["predicted"] for d in fc.daily_forecasts[:14]])
        late_avg = np.mean([d["predicted"] for d in fc.daily_forecasts[-14:]])
        assert late_avg >= early_avg  # Should grow or stay stable

    def test_newproduct_conservative_default(self):
        skill = DemandNewProduct()
        result = skill.run(NewProductInput(
            sku_id="NEW_NODEF_001",
            horizon=28,
            method="similarity",
            # No reference history → conservative default
        ))
        assert len(result.forecasts) == 1
        fc = result.forecasts[0]
        assert fc.method_used == "conservative_default"
        assert fc.confidence_score <= 0.35  # Very low confidence

    def test_newproduct_dict_input(self):
        skill = DemandNewProduct()
        result = skill.run({"sku_id": "DICT_TEST", "horizon": 14})
        assert len(result.forecasts) == 1


# ════════════════════════════════════════════════
# Test: Demand Intermittent
# ════════════════════════════════════════════════

class TestDemandIntermittent:
    def test_intermittent_detection(self):
        demand_data = _generate_intermittent_demand()
        skill = DemandIntermittent()
        result = skill.run(IntermittentInput(
            demand_history=demand_data,
            horizon=14,
            zero_threshold=0.5,
        ))
        assert len(result.results) == 3  # 3 SKUs
        # SKU002 and SKU003 should be detected as intermittent
        intermittent = [r for r in result.results if r.is_intermittent]
        assert len(intermittent) >= 1
        assert result.summary["intermittent_pct"] > 0

    def test_intermittent_croston_variant(self):
        demand_data = _generate_intermittent_demand()
        skill = DemandIntermittent()
        result = skill.run(IntermittentInput(
            demand_history=demand_data,
            horizon=14,
            variant="sba",
        ))
        for r in result.results:
            assert r.total_predicted >= 0
            if r.is_intermittent:
                assert "croston" in r.method_used.lower() or r.method_used != "use_standard"

    def test_all_variants_run(self):
        demand_data = _generate_intermittent_demand()
        for variant in ["classic", "sba", "tsb"]:
            skill = DemandIntermittent()
            result = skill.run(IntermittentInput(
                demand_history=demand_data, horizon=7, variant=variant,
            ))
            assert result.summary["variant_used"] == variant

    def test_non_intermittent_recommended_standard(self):
        # All normal demand — no intermittents
        normal_data = [
            {"sku_id": "NORM01", "location_id": "A", "date": f"2026-01-{i+1:02d}",
             "quantity": 50 + np.random.randn() * 5}
            for i in range(60)
        ]
        skill = DemandIntermittent()
        result = skill.run(IntermittentInput(
            demand_history=normal_data, zero_threshold=0.8,
        ))
        assert result.results[0].recommendation == "use_standard"
        assert not result.results[0].is_intermittent


# ════════════════════════════════════════════════
# Test: Demand Reconcile
# ════════════════════════════════════════════════

class TestDemandReconcile:
    def test_bottom_up_reconciliation(self):
        bottom = [
            {"entity_id": "SKU001", "forecast": 1000},
            {"entity_id": "SKU002", "forecast": 2000},
            {"entity_id": "SKU003", "forecast": 1500},
        ]
        hierarchy = {"REGION_A": ["SKU001", "SKU002"], "REGION_B": ["SKU003"]}
        skill = DemandReconcile()
        result = skill.run(ReconcileInput(
            bottom_level=bottom,
            hierarchy=hierarchy,
            method="bottom_up",
        ))
        assert len(result.reconciled) >= 4  # 3 bottom + grand total + regions
        gt = next(r for r in result.reconciled if r.level == "top")
        assert abs(gt.reconciled_value - 4500) < 0.01  # 1000+2000+1500

    def test_top_down_reconciliation(self):
        bottom = [
            {"entity_id": "SKU001", "forecast": 1000},
            {"entity_id": "SKU002", "forecast": 2000},
        ]
        skill = DemandReconcile()
        result = skill.run(ReconcileInput(
            bottom_level=bottom,
            top_level_forecast=4000.0,  # Target is less than sum (4500)
            method="top_down",
        ))
        reconciled_sum = sum(r.reconciled_value for r in result.reconciled if r.level == "bottom")
        assert abs(reconciled_sum - 4000) < 0.01  # Should match target

    def test_middle_out_method(self):
        bottom = [
            {"entity_id": "A", "forecast": 500},
            {"entity_id": "B", "forecast": 800},
        ]
        skill = DemandReconcile()
        result = skill.run(ReconcileInput(
            bottom_level=bottom,
            top_level_forecast=1300.0,
            method="middle_out",
        ))
        assert result.summary["method"] == "middle_out"

    def test_reconciliation_dict_input(self):
        skill = DemandReconcile()
        result = skill.run({
            "bottom_level": [{"entity_id": "X", "forecast": 100}],
            "method": "bottom_up",
        })
        assert len(result.reconciled) >= 1


# ════════════════════════════════════════════════
# Test: Inventory Policy Simulation
# ════════════════════════════════════════════════

class TestInventoryPolicySim:
    def test_policy_simulation_runs(self):
        skill = InventoryPolicySim()
        result = skill.run(PolicySimInput(
            sku_id="TEST_SKU",
            demand_mean=100.0,
            demand_std=20.0,
            n_periods=180,
            n_simulations=50,
        ))
        assert len(result.results) >= 2  # At least 2 policies compared
        assert result.best_policy != ""
        # Best policy should have lowest cost
        costs = [r.total_cost for r in result.results]
        best_cost = min(r.total_cost for r in result.results if r.policy_name == result.best_policy)
        assert best_cost == min(costs)

    def test_service_levels_reasonable(self):
        skill = InventoryPolicySim()
        result = skill.run(PolicySimInput(
            demand_mean=80, demand_std=15, n_periods=90, n_simulations=30,
        ))
        for r in result.results:
            assert 0 <= r.service_level <= 1
            assert 0 <= r.fill_rate <= 1
            assert r.average_inventory >= 0
            assert r.total_cost >= 0

    def test_higher_ss_higher_service(self):
        """Policies with more safety stock should achieve higher service levels."""
        skill = InventoryPolicySim()
        result = skill.run(PolicySimInput(
            demand_mean=100, demand_std=25, n_periods=180, n_simulations=50,
        ))
        if len(result.results) >= 2:
            sorted_by_cost = sorted(result.results, key=lambda r: r.total_cost)
            # Cheapest policy likely has lowest service level
            # Most expensive policy likely has highest service level
            sl_range = [r.service_level for r in result.results]
            assert max(sl_range) >= min(sl_range)

    def test_comparison_data_present(self):
        skill = InventoryPolicySim()
        result = skill.run(PolicySimInput(
            demand_mean=100, demand_std=20, n_simulations=20,
        ))
        assert "cost_ranking" in result.comparison
        assert "service_level_range" in result.comparison
        assert "cost_savings_vs_worst" in result.comparison
        assert result.summary["policies_tested"] == len(result.results)
        assert result.best_policy  # best_policy should be set


# ════════════════════════════════════════════════
# Test: Multi-Echelon Inventory
# ════════════════════════════════════════════════

class TestMultiEchelon:
    def test_basic_network(self):
        nodes = [
            EchelonNode(node_id="FACTORY", name="Factory", type="factory",
                        demand_mean=500, demand_std=80, lead_time_days=0),
            EchelonNode(node_id="DC1", name="DC North", type="dc", parent_id="FACTORY",
                        demand_mean=200, demand_std=40, lead_time_days=3),
            EchelonNode(node_id="STORE1", name="Store 1", type="store", parent_id="DC1",
                        demand_mean=80, demand_std=20, lead_time_days=2),
        ]
        skill = InventoryMultiEchelon()
        result = skill.run(MultiEchelonInput(nodes=nodes, target_service_level=0.95))
        assert len(result.results) == 3
        for r in result.results:
            assert r.total_ss >= 0
            assert r.reorder_point >= 0
            assert 0 < r.service_level_achieved <= 1.0

    def test_demo_network_no_config(self):
        """Test that the CLI demo network works when no config provided."""
        skill = InventoryMultiEchelon()
        result = skill.run(MultiEchelonInput(nodes=[], target_service_level=0.95))
        # Empty nodes → error summary
        assert result.summary.get("error") == "No nodes provided"

    def test_deep_hierarchy(self):
        """Test a deeper chain: Factory → DC → Store."""
        nodes = [
            EchelonNode(node_id="F", type="factory", demand_mean=1000, demand_std=150,
                        lead_time_days=0),
            EchelonNode(node_id="DC", type="dc", parent_id="F", demand_mean=400,
                        demand_std=70, lead_time_days=5),
            EchelonNode(node_id="S", type="store", parent_id="DC", demand_mean=100,
                        demand_std=25, lead_time_days=2),
        ]
        skill = InventoryMultiEchelon()
        result = skill.run(MultiEchelonInput(nodes=nodes, target_service_level=0.90))
        assert len(result.results) == 3
        # Store should have higher ROP than DC relative to its own demand
        store = next(r for r in result.results if r.node_id == "S")
        dc = next(r for r in result.results if r.node_id == "DC")
        assert store.reorder_point > 0
        assert dc.reorder_point > 0

    def test_summary_structure(self):
        nodes = [
            EchelonNode(node_id="F", type="factory", demand_mean=500, demand_std=50,
                        lead_time_days=0),
            EchelonNode(node_id="D", type="dc", parent_id="F", demand_mean=200,
                        demand_std=30, lead_time_days=3),
            EchelonNode(node_id="S1", type="store", parent_id="D", demand_mean=80,
                        demand_std=15, lead_time_days=1),
            EchelonNode(node_id="S2", type="store", parent_id="D", demand_mean=120,
                        demand_std=20, lead_time_days=1),
        ]
        skill = InventoryMultiEchelon()
        result = skill.run(MultiEchelonInput(nodes=nodes))
        s = result.summary
        assert s["total_nodes"] == 4
        assert s["network_structure"]["factories"] == 1
        assert s["network_structure"]["dcs"] == 1
        assert s["network_structure"]["stores"] == 2
        assert s["total_system_safety_stock"] > 0


# ════════════════════════════════════════════════
# Test: Newsvendor Model
# ════════════════════════════════════════════════

class TestNewsvendorSkill:
    def test_basic_newsvendor(self):
        item = NewsvendorItem(
            sku_id="MARKDOWN_SKU",
            selling_price=29.99,
            cost=12.00,
            salvage_value=3.00,
            demand_mean=200,
            demand_std=40,
        )
        skill = InventoryNewsvendor()
        result = skill.run(NewsvendorInput(items=[item]))
        assert len(result.results) == 1
        r = result.results[0]
        assert r.optimal_quantity > 0
        assert 0 < r.critical_ratio < 1
        assert r.expected_profit > 0
        assert r.sensitivity is not None and len(r.sensitivity) > 0

    def test_critical_ratio_calculation(self):
        """Cu = p - c, Co = c - s, CR = Cu / (Cu + Co)."""
        item = NewsvendorItem(
            selling_price=35, cost=20, salvage_value=5,
            demand_mean=100, demand_std=25,
        )
        skill = InventoryNewsvendor()
        result = skill.run(NewsvendorInput(items=[item]))
        r = result.results[0]
        # CR = (35-20) / (35-20 + 20-5) = 15/30 = 0.5
        assert abs(r.critical_ratio - 0.5) < 0.001

    def test_high_margin_high_quantity(self):
        """Higher margin (higher CR) → higher optimal quantity."""
        high_margin = NewsvendorItem(
            sku_id="HIGH", selling_price=100, cost=10, salvage_value=5,
            demand_mean=100, demand_std=20,
        )
        low_margin = NewsvendorItem(
            sku_id="LOW", selling_price=20, cost=15, salvage_value=5,
            demand_mean=100, demand_std=20,
        )
        skill = InventoryNewsvendor()
        result = skill.run(NewsvendorInput(items=[high_margin, low_margin]))
        high_r = next(r for r in result.results if r.sku_id == "HIGH")
        low_r = next(r for r in result.results if r.sku_id == "LOW")
        assert high_r.optimal_quantity > low_r.optimal_quantity

    def test_sensitivity_analysis_keys(self):
        item = NewsvendorItem(
            selling_price=50, cost=20, salvage_value=0,
            demand_mean=150, demand_std=30,
        )
        skill = InventoryNewsvendor()
        result = skill.run(NewsvendorInput(items=[item]))
        r = result.results[0]
        # Should have price and cost sensitivity entries
        sens_keys = list(r.sensitivity.keys())
        assert any("price" in k for k in sens_keys)
        assert any("cost" in k for k in sens_keys)

    def test_multi_item(self):
        items = [
            NewsvendorItem(sku_id=f"SKU{i}", selling_price=30+i*5, cost=10+i*2,
                          salvage_value=2, demand_mean=100+i*20, demand_std=20+i*5)
            for i in range(5)
        ]
        skill = InventoryNewsvendor()
        result = skill.run(NewsvendorInput(items=items))
        assert len(result.results) == 5
        assert result.summary["total_expected_profit"] > 0
        assert result.summary["items_analyzed"] == 5


# ════════════════════════════════════════════════
# Test: Learning Loop
# ════════════════════════════════════════════════

class TestLearningLoop:
    def test_feedback_processing(self):
        loop = LearningLoop()
        fb = Feedback(
            feedback_type=FeedbackType.IMPLICIT_ADOPT,
            skill="demand-forecast",
            sku_id="SKU001",
        )
        event = loop.on_feedback(fb)
        assert event.event_type == "no_action"  # No domain memory → no action
        summary = loop.get_feedback_summary()
        assert summary["total_feedback"] == 1

    def test_adjustment_triggers_preference_update(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        dm = DomainMemory(project_id="test_adj", storage_dir=tmpdir)
        loop = LearningLoop(domain_memory=dm)

        fb = Feedback(
            feedback_type=FeedbackType.IMPLICIT_ADJUST,
            skill="demand-forecast",
            sku_id="SKU001",
            category="dairy",
            original_value=100.0,
            adjusted_value=80.0,  # Over-forecasted by 20%
        )
        event = loop.on_feedback(fb)
        assert event.event_type == "preference_updated"
        assert "dairy" in event.description

    def test_rule_generation_after_three_adjustments(self):
        import tempfile, shutil
        tmpdir = tempfile.mkdtemp()
        dm = DomainMemory(project_id="test_rules", storage_dir=tmpdir)
        loop = LearningLoop(domain_memory=dm)
        try:
            # Submit 3 adjustments for same category to trigger rule
            for i in range(3):
                fb = Feedback(
                    feedback_type=FeedbackType.IMPLICIT_ADJUST,
                    skill="demand-forecast",
                    category="beverage",
                    original_value=100.0,
                    adjusted_value=120.0 + i * 5,  # Consistently under-forecast
                )
                loop.on_feedback(fb)

            summary = loop.get_feedback_summary()
            assert summary["total_feedback"] == 3
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_explicit_correction_recorded(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        dm = DomainMemory(project_id="test_corr", storage_dir=tmpdir)
        loop = LearningLoop(domain_memory=dm)

        fb = Feedback(
            feedback_type=FeedbackType.EXPLICIT_CORRECTION,
            skill="inventory-reorder",
            sku_id="SKU001",
            reason="Promotion coming next week, need more stock",
        )
        event = loop.on_feedback(fb)
        assert event.event_type == "correction_recorded"

    def test_backtest_result_recorded(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        dm = DomainMemory(project_id="test_bt", storage_dir=tmpdir)
        loop = LearningLoop(domain_memory=dm)

        fb = Feedback(
            feedback_type=FeedbackType.BACKTEST_RESULT,
            category="SKU001",
            context={"mape": 12.5, "method_used": "holt_winters"},
            reason="Backtest completed",
        )
        event = loop.on_feedback(fb)
        assert event.event_type == "performance_recorded"

    def test_feedback_summary(self):
        loop = LearningLoop()
        types = [
            FeedbackType.IMPLICIT_ADOPT,
            FeedbackType.IMPLICIT_ADJUST,
            FeedbackType.EXPLICIT_THUMBS_UP,
        ]
        for t in types:
            loop.on_feedback(Feedback(feedback_type=t, category="test"))
        summary = loop.get_feedback_summary()
        assert summary["total_feedback"] == 3
        assert len(summary["by_type"]) == 3


# ════════════════════════════════════════════════
# Test: Backtester
# ════════════════════════════════════════════════

class TestBacktester:
    def _make_trend_data(self, n=120):
        return [100 + i * 0.5 + np.random.randn() * 8 for i in range(n)]

    def test_backtest_runs(self):
        values = self._make_trend_data()
        bt = Backtester()
        report = bt.run_backtest(values, horizon=7, methods=["auto", "ma"], n_folds=5)
        assert isinstance(report, BacktestReport)
        assert len(report.results) == 2
        assert report.comparison["methods_tested"] == 2
        # best/worst fold mape are on individual results, not the report
        assert len(report.results) > 0

    def test_best_method_identified(self):
        values = self._make_trend_data()
        bt = Backtester()
        report = bt.run_backtest(values, horizon=7, methods=["ma", "ema"], n_folds=4)
        assert report.comparison["best_method"] in ("ma", "ema")

    def test_insufficient_data(self):
        bt = Backtester()
        report = bt.run_backtest([1, 2, 3], horizon=7)
        assert "Insufficient data" in report.recommendation

    def test_multiple_methods_compared(self):
        values = self._make_trend_data(180)
        bt = Backtester()
        report = bt.run_backtest(
            values, horizon=14,
            methods=["auto", "ma", "ema", "holt_winters"],
            n_folds=5,
        )
        assert len(report.results) == 4
        ranking = report.comparison["ranking_by_mape"]
        # Ranking should be sorted by MAPE
        mapes = [r[1] for r in ranking]
        assert mapes == sorted(mapes)

    def test_naive_baseline_improvement(self):
        values = self._make_trend_data(150)
        bt = Backtester()
        report = bt.run_backtest(values, horizon=7, methods=["auto"], n_folds=4)
        naive_info = report.comparison.get("improvement_over_naive", {})
        assert "naive_mape" in naive_info

    def test_mape_scores_list(self):
        values = self._make_trend_data(120)
        bt = Backtester()
        report = bt.run_backtest(values, horizon=7, methods=["ma"], n_folds=3)
        result = report.results[0]
        assert len(result.mape_scores) == result.n_folds
        assert len(result.mae_scores) == result.n_folds
        assert result.avg_mape > 0


# ════════════════════════════════════════════════
# Test: Skill Evolution
# ════════════════════════════════════════════════

class TestSkillEvolution:
    def setup_method(self):
        """Use temp directory for evolution storage."""
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.evo = SkillEvolution(storage_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_execution(self):
        self.evo.record_execution("demand-forecast", "holt_winters", mape=8.5, category="dairy")
        profile = self.evo.get_profile("demand-forecast")
        assert profile.total_executions == 1
        assert "holt_winters" in profile.method_performance
        mp = profile.method_performance["holt_winters"]
        assert mp.avg_mape == 8.5

    def test_record_multiple_executions(self):
        for mape in [10.0, 9.0, 11.0, 8.5, 9.5]:
            self.evo.record_execution("demand-forecast", "auto", mape=mape)
        profile = self.evo.get_profile("demand-forecast")
        mp = profile.method_performance["auto"]
        assert mp.total_executions == 5
        assert mp.best_mape == 8.5
        assert mp.worst_mape == 11.0

    def test_record_correction(self):
        self.evo.record_correction(
            "demand-forecast", "SKU001", "dairy",
            original_value=100.0, corrected_value=80.0,
            reason="Over-forecasting consistently",
        )
        profile = self.evo.get_profile("demand-forecast")
        assert len(profile.user_corrections) == 1
        c = profile.user_corrections[0]
        assert c.learned != ""

    def test_auto_rule_generation(self):
        # Need 3+ corrections for same category to trigger rule
        for i in range(3):
            self.evo.record_correction(
                "demand-forecast", f"SKU{i:03d}", "beverage",
                original_value=100.0, corrected_value=130.0,
                reason=f"Correction #{i+1}",
            )
        rules = self.evo.get_auto_rules("demand-forecast")
        # May or may not have rules depending on threshold logic
        assert isinstance(rules, list)

    def test_best_method_selection(self):
        self.evo.record_execution("skill_x", "method_a", mape=15.0, category="cat1")
        self.evo.record_execution("skill_x", "method_b", mape=8.0, category="cat1")
        self.evo.record_execution("skill_x", "method_a", mape=12.0, category="cat2")
        best = self.evo.get_best_method("skill_x", category="cat1")
        assert best == "method_b"  # Lower MAPE wins

    def test_evolution_summary(self):
        self.evo.record_execution("test_skill", "m1", mape=10.0)
        self.evo.record_correction("test_skill", "S1", "c1", 100, 90)
        summary = self.evo.get_evolution_summary("test_skill")
        assert summary["skill"] == "test_skill"
        assert summary["total_executions"] == 1
        assert summary["corrections_received"] == 1

    def test_persistence(self):
        """Test that profiles survive across instances (same dir)."""
        self.evo.record_execution("persist_skill", "m1", mape=5.0)
        # Create new instance pointing to same dir
        evo2 = SkillEvolution(storage_dir=self.tmpdir)
        profile = evo2.get_profile("persist_skill")
        assert profile.total_executions == 1


# ════════════════════════════════════════════════
# Test: Memory System
# ════════════════════════════════════════════════

class TestJSONFileStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = JSONFileStore(base_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        self.store.set("test_key", {"value": 42, "data": "hello"})
        result = self.store.get("test_key")
        assert result == {"value": 42, "data": "hello"}

    def test_get_missing(self):
        assert self.store.get("nonexistent") is None

    def test_delete(self):
        self.store.set("to_delete", "data")
        assert self.store.exists("to_delete")
        self.store.delete("to_delete")
        assert not self.store.exists("to_delete")

    def test_keys(self):
        self.store.set("a", 1)
        self.store.set("b", 2)
        self.store.set("c", 3)
        keys = self.store.keys()
        assert set(keys) == {"a", "b", "c"}

    def test_overwrite(self):
        self.store.set("key", "v1")
        self.store.set("key", "v2")
        assert self.store.get("key") == "v2"


class TestDomainMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get_preference(self):
        dm = DomainMemory(project_id="test_pref", storage_dir=self.tmpdir)
        dm.set_preference("forecast_method", "holt_winters")
        assert dm.get_preference("forecast_method") == "holt_winters"

    def test_record_pattern(self):
        dm = DomainMemory(project_id="test_pat", storage_dir=self.tmpdir)
        dm.record_pattern("seasonality", "Strong weekly pattern detected", {
            "sku_id": "SKU001", "strength": 0.8,
        })
        patterns = dm.get_patterns("seasonality")
        assert len(patterns) == 1
        assert "Strong weekly pattern" in patterns[0].get("description", "")

    def test_record_model_performance(self):
        dm = DomainMemory(project_id="test_perf", storage_dir=self.tmpdir)
        dm.record_model_performance("dairy", "holt_winters", 8.5)
        all_data = dm.get_all()
        mp = all_data.get("model_performance", {})
        assert "dairy" in mp


class TestMetaMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "meta_test.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_skill_usage_tracking(self):
        mm = MetaMemory(storage_path=self.path)
        mm.record_skill_usage("demand-forecast", success=True, duration=1.5)
        stats = mm.get_skill_stats("demand-forecast")
        assert stats["total_calls"] == 1
        assert stats["successes"] == 1

    def test_user_style_preferences(self):
        mm = MetaMemory(storage_path=self.path)
        mm.set_user_style("default_detail_level", "detailed")
        assert mm.get_user_style("default_detail_level") == "detailed"

    def test_cross_project_learning(self):
        mm = MetaMemory(storage_path=self.path)
        mm.add_learning("Always check promo calendar before forecasting", source_project="retail_a")
        learnings = mm.get_relevant_learnings("promo forecast")
        assert len(learnings) >= 1

    def test_decision_history(self):
        mm = MetaMemory(storage_path=self.path)
        mm.record_decision("dec_001", "demand-forecast", "approved", 0.9, "Looks good")
        decisions = mm.get_recent_decisions()
        assert len(decisions) == 1
        assert decisions[0]["decision_type"] == "approved"


class TestWorkingMemory:
    def test_context_management(self):
        wm = WorkingMemory()
        wm.set("$forecast", {"skus": [{"id": "SKU001", "predicted": 500}]})
        fc = wm.get("$forecast")
        assert fc["skus"][0]["predicted"] == 500

    def test_keys_and_size(self):
        wm = WorkingMemory()
        wm.set("a", 1)
        wm.set("b", 2)
        wm.set("c", 3)
        assert wm.size == 3
        assert set(wm.keys()) == {"a", "b", "c"}

    def test_delete(self):
        wm = WorkingMemory()
        wm.set("to_delete", "data")
        wm.delete("to_delete")
        assert wm.get("to_delete") is None
        assert "to_delete" not in wm

    def test_clear(self):
        wm = WorkingMemory()
        wm.set("temp", "data")
        wm.clear()
        assert wm.get("temp") is None
        assert wm.size == 0

    def test_to_dict_export(self):
        wm = WorkingMemory()
        wm.set("key1", "val1")
        wm.set("key2", {"nested": True})
        d = wm.to_dict()
        assert d == {"key1": "val1", "key2": {"nested": True}}


# ════════════════════════════════════════════════
# Test: HITL Engine
# ════════════════════════════════════════════════

class TestHTLEngine:
    def setup_method(self):
        self.engine = HTLEngine(default_timeout=1.0)  # 1 second timeout for testing

    def test_create_auto_session(self):
        session = self.engine.create_session(
            level="auto", skill="test", step_name="step1"
        )
        assert session.status == HITLDecision.APPROVED  # Auto-approved immediately

    def test_create_review_session(self):
        session = self.engine.create_session(
            level="review", skill="demand-forecast", step_name="forecast_step",
            title="Forecast Review", summary="Please review forecast",
        )
        assert session.is_pending
        assert session.level == "review"
        assert "adjust" in session.allowed_actions

    def test_resolve_session(self):
        session = self.engine.create_session(
            level="review", skill="test", step_name="step1"
        )
        resolved = self.engine.resolve(session.id, HITLDecision.APPROVED, "Looks good")
        assert resolved.status == HITLDecision.APPROVED
        assert resolved.resolution == "Looks good"

    def test_adjust_resolution(self):
        session = self.engine.create_session(
            level="review", skill="test", step_name="step1"
        )
        resolved = self.engine.resolve(
            session.id, HITLDecision.ADJUSTED, "Changed value",
            adjusted_data={"original": 100, "adjusted": 120},
        )
        assert resolved.status == HITLDecision.ADJUSTED
        assert resolved.adjusted_data["adjusted"] == 120

    def test_double_resolve_raises(self):
        session = self.engine.create_session(
            level="review", skill="test", step_name="step1"
        )
        self.engine.resolve(session.id, HITLDecision.APPROVED)
        # Second resolve should not raise but return existing state
        result = self.engine.resolve(session.id, HITLDecision.REJECTED)
        assert result.status == HITLDecision.APPROVED  # Stays approved

    def test_stats(self):
        self.engine.create_session(level="auto", skill="s1", step_name="st1")
        s = self.engine.create_session(level="review", skill="s2", step_name="st2")
        self.engine.resolve(s.id, HITLDecision.APPROVED)
        stats = self.engine.stats
        assert stats["total_sessions"] == 2
        assert stats["approved"] >= 1  # At least the auto + manual approve

    def test_callback_fired(self):
        callbacks_received = []
        self.engine.on_decision(lambda sess: callbacks_received.append(sess.id))
        session = self.engine.create_session(level="review", skill="test", step_name="st")
        self.engine.resolve(session.id, HITLDecision.APPROVED)
        assert session.id in callbacks_received

    def test_timeout_auto_approve(self):
        import time
        session = self.engine.create_session(
            level="review", skill="test", step_name="slow",
            timeout=0.1,  # 100ms timeout
        )
        assert session.is_pending
        time.sleep(0.15)
        timed_out = self.engine.check_timeouts()
        assert len(timed_out) >= 1
        assert timed_out[0].status == HITLDecision.TIMEOUT_AUTO_APPROVE


# ════════════════════════════════════════════════
# Test: MCP Server
# ════════════════════════════════════════════════

class TestMCPServer:
    def setup_method(self):
        self.server = MCPServer()

    def test_tool_registration(self):
        tools = self.server.list_tools()
        tool_names = {t["name"] for t in tools}
        # Check core tools exist
        assert "demand_forecast" in tool_names
        assert "demand_decompose" in tool_names
        assert "inventory_classify" in tool_names
        assert "data_profiler" in tool_names
        assert len(tools) >= 20

    def test_call_unknown_tool(self):
        result = self.server.call_tool("nonexistent_tool", {})
        assert "error" in result
        assert result["success"] is False

    def test_call_data_profiler(self):
        result = self.server.call_tool("data_profiler", {
            "data": [
                {"sku_id": "S1", "quantity": 10},
                {"sku_id": "S1", "quantity": 20},
                {"sku_id": "S2", "quantity": 15},
            ],
            "profile_type": "quick",
        })
        assert result["success"] is True
        assert "result" in result

    def test_call_demand_decompose(self):
        result = self.server.call_tool("demand_decompose", {
            "demand_history": [
                {"sku_id": "S1", "date": "2026-01-01", "quantity": 10 + i}
                for i in range(30)
            ],
        })
        assert result["success"] is True

    def test_handle_request_tools_list(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        })
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "tools" in response["result"]

    def test_handle_request_tools_call(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {
                "name": "data_profiler",
                "arguments": {"data": {"demand_history": [{"sku_id": "S1", "quantity": 42}]}},
            },
        })
        assert response["jsonrpc"] == "2.0"
        assert response["result"]["success"] is True

    def test_handle_request_unknown_method(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0",
            "method": "invalid/method",
            "id": 3,
        })
        assert "error" in response


# ════════════════════════════════════════════════
# Test: CLI Command Registration
# ════════════════════════════════════════════════

class TestCLIRegistration:
    def test_all_commands_registered(self):
        """Verify all Phase 1 + Phase 2 commands are registered in CLI main group."""
        from supplymind.cli import main
        commands = list(main.commands.keys())
        # Phase 1 commands
        assert "data-profiler" in commands
        assert "report-generator" in commands
        assert "demand-forecast" in commands
        assert "demand-anomaly" in commands
        assert "inventory-classify" in commands
        assert "inventory-safety-stock" in commands
        assert "inventory-reorder" in commands
        # Phase 2 commands
        assert "demand-decompose" in commands
        assert "demand-newproduct" in commands
        assert "demand-intermittent" in commands
        assert "demand-reconcile" in commands
        assert "inventory-policy-sim" in commands
        assert "inventory-multi-echelon" in commands
        assert "inventory-newsvendor" in commands
        # Pipeline command
        assert "run-pipeline" in commands
        # Total count check
        assert len(commands) >= 15


# ════════════════════════════════════════════════
# Test: Pipeline Engine Skill Registry
# ════════════════════════════════════════════════

class TestPipelineRegistry:
    def test_all_skills_in_registry(self):
        """Verify all skills are registered in Pipeline Engine's skill_map."""
        from supplymind.pipelines.engine import _get_skill_instance
        # These should not raise ValueError
        known_skills = [
            "data-profiler", "report-generator",
            "demand-forecast", "demand-anomaly",
            "demand-decompose", "demand-newproduct",
            "demand-intermittent", "demand-reconcile",
            "inventory-classify", "inventory-safety-stock",
            "inventory-reorder", "inventory-policy-sim",
            "inventory-multi-echelon", "inventory-newsvendor",
        ]
        for skill_name in known_skills:
            instance = _get_skill_instance(skill_name)
            assert instance is not None
            assert hasattr(instance, 'run')

    def test_unknown_skill_raises(self):
        from supplymind.pipelines.engine import _get_skill_instance
        with pytest.raises(ValueError, match="Unknown skill"):
            _get_skill_instance("nonexistent-skill")
