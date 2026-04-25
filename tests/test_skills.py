"""
Skill integration tests — validates all 7 Skills work end-to-end.
"""

import json
import os
import tempfile

import numpy as np
import pytest

from supplymind.skills.common.data_profiler.main import DataProfiler
from supplymind.skills.common.data_profiler.schema import ProfilerInput
from supplymind.skills.demand.forecast.main import DemandForecast
from supplymind.skills.demand.forecast.schema import ForecastInput
from supplymind.skills.demand.anomaly.main import DemandAnomaly
from supplymind.skills.demand.anomaly.schema import AnomalyInput
from supplymind.skills.inventory.classify.main import InventoryClassify
from supplymind.skills.inventory.classify.schema import ClassifyInput
from supplymind.skills.inventory.safety_stock.main import InventorySafetyStock
from supplymind.skills.inventory.safety_stock.schema import SafetyStockInput
from supplymind.skills.inventory.reorder.main import InventoryReorder
from supplymind.skills.inventory.reorder.schema import ReorderInput
from supplymind.skills.common.report_generator.main import ReportGenerator
from supplymind.skills.common.report_generator.schema import ReportInput


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


class TestDataProfiler:
    def test_profiler_runs(self):
        demand_data = _generate_demand_dicts()
        profiler = DataProfiler()
        result = profiler.run(ProfilerInput(data={"demand_history": demand_data}))
        assert result.total_records > 0
        assert result.unique_skus > 0
        assert 0 <= result.data_quality_score <= 100
        assert len(result.sku_stats) == 3

    def test_recommendations_generated(self):
        demand_data = _generate_demand_dicts()
        profiler = DataProfiler()
        result = profiler.run(ProfilerInput(data={"demand_history": demand_data}))
        assert len(result.recommendations) > 0

    def test_empty_data(self):
        profiler = DataProfiler()
        result = profiler.run(ProfilerInput(data={}))
        assert result.total_records == 0
        assert "No demand data" in result.recommendations[0]


class TestDemandForecast:
    def test_forecast_runs(self):
        demand_data = _generate_demand_dicts()
        forecaster = DemandForecast()
        result = forecaster.run(ForecastInput(
            demand_history=demand_data,
            horizon=14,
            method="auto",
        ))
        assert len(result.forecasts) == 3  # 3 SKUs
        assert result.horizon == 14
        for fc in result.forecasts:
            assert fc.total_predicted > 0
            assert len(fc.daily_forecasts) == 14

    def test_ma_method(self):
        demand_data = _generate_demand_dicts()
        forecaster = DemandForecast()
        result = forecaster.run(ForecastInput(
            demand_history=demand_data, horizon=7, method="ma",
        ))
        assert result.method == "ma"
        assert len(result.forecasts) > 0

    def test_sku_filter(self):
        demand_data = _generate_demand_dicts()
        forecaster = DemandForecast()
        result = forecaster.run(ForecastInput(
            demand_history=demand_data, horizon=7,
            sku_filter=["SKU001"],
        ))
        assert len(result.forecasts) == 1
        assert result.forecasts[0].sku_id == "SKU001"


class TestDemandAnomaly:
    def test_anomaly_detection(self):
        # Inject an outlier
        demand_data = _generate_demand_dicts()
        demand_data[30]["quantity"] = 99999.0  # Outlier!

        detector = DemandAnomaly()
        result = detector.run(AnomalyInput(
            demand_history=demand_data, method="zscore", threshold=2.5,
        ))
        assert result.original_count == len(demand_data)
        assert result.removed_count >= 0
        assert len(result.per_sku_summary) > 0

    def test_remove_action(self):
        demand_data = _generate_demand_dicts()
        demand_data[40]["quantity"] = -100.0  # Invalid negative value

        detector = DemandAnomaly()
        result = detector.run(AnomalyInput(
            demand_history=demand_data, action="remove",
        ))
        assert len(result.cleaned_demand_history) < result.original_count


class TestInventoryClassify:
    def test_abc_xyz_classification(self):
        items = []
        for i in range(10):
            values = [50 + np.random.randn() * (i + 1) * 5 for _ in range(60)]
            items.append({
                "item_id": f"ITEM{i:03d}",
                "revenue": (10 - i) * 100 + np.random.randint(-10, 10),
                "demand_values": [max(0, v) for v in values],
            })

        classifier = InventoryClassify()
        result = classifier.run(ClassifyInput(items=items))
        assert len(result.abc_result.get("items", [])) == 10
        assert len(result.matrix) == 9  # 3x3 matrix
        assert "AX" in result.matrix


class TestSafetyStock:
    def test_safety_stock_calculation(self):
        items = []
        for i in range(5):
            values = [80 + np.random.randn() * 15 for _ in range(60)]
            items.append({
                "item_id": f"SKU{i+1:03d}",
                "demand_values": [max(0, v) for v in values],
                "lead_time_days": 5 + i,
            })

        calc = InventorySafetyStock()
        result = calc.run(SafetyStockInput(items=items, service_level=0.95))
        assert len(result.results) == 5
        for r in result.results:
            assert r.safety_stock >= 0
            assert r.reorder_point >= 0


class TestInventoryReorder:
    def test_reorder_suggestions(self):
        forecasts = []
        for i in range(3):
            forecasts.append({
                "sku_id": f"SKU{i+1:03d}",
                "location_id": "STORE_A",
                "total_predicted": 500 + i * 200,
                "avg_daily_predicted": 35 + i * 14,
                "mape": 8.0 + i * 3,
                "confidence_score": 0.9 - i * 0.05,
            })

        inventory = [
            {"sku_id": "SKU001", "location_id": "STORE_A", "available": 200},
            {"sku_id": "SKU002", "location_id": "STORE_A", "available": 400},
            {"sku_id": "SKU003", "location_id": "STORE_A", "available": 800},
        ]

        sku_master = [
            {"sku_id": "SKU001", "unit_cost": 20},
            {"sku_id": "SKU002", "unit_cost": 12},
            {"sku_id": "SKU003", "unit_cost": 35},
        ]

        ss_list = [
            {"sku_id": "SKU001", "safety_stock": 80, "reorder_point": 350},
            {"sku_id": "SKU002", "safety_stock": 50, "reorder_point": 250},
            {"sku_id": "SKU003", "safety_stock": 120, "reorder_point": 450},
        ]

        reorder = InventoryReorder()
        result = reorder.run(ReorderInput(
            forecasts=forecasts,
            inventory_snapshots=inventory,
            sku_master=sku_master,
            safety_stocks=ss_list,
            horizon=14,
        ))
        assert len(result.suggestions) == 3
        # SKU001 should need reorder (stock 200 < predicted ~700)
        high_urgency = [s for s in result.suggestions if s.urgency == "high"]
        assert len(high_urgency) >= 1
        assert result.summary["total_order_quantity"] > 0


class TestReportGenerator:
    def test_markdown_report(self):
        sections = [
            {"type": "summary", "title": "Test Summary", "data": {"Key": "Value", "Count": 42}},
            {"type": "table", "title": "Test Table", "data": {
                "headers": ["A", "B"], "rows": [[1, 2], [3, 4]]
            }},
        ]
        generator = ReportGenerator()
        result = generator.run(ReportInput(title="Test Report", sections=sections))
        assert "# Test Report" in result.content
        assert "42" in result.content
        assert result.format == "markdown"

    def test_html_report(self):
        sections = [{"type": "summary", "data": {"Status": "OK"}}]
        generator = ReportGenerator()
        result = generator.run(ReportInput(sections=sections, format="html"))
        assert "<html" in result.content.lower() or "<!DOCTYPE" in result.content
        assert result.format == "html"
