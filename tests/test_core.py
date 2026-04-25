"""
Core algorithm tests — validates all 5 core modules.
"""

import math
import numpy as np
import pytest

from supplymind.core.timeseries import (
    moving_average, exponential_moving_average, holt_winters,
    stl_decompose, croston_forecast, auto_forecast,
)
from supplymind.core.inventory_models import (
    eoq, rop, ss_service_level_full, newsvendor_optimal_order, s_S_policy_simulation,
)
from supplymind.core.optimization import (
    allocate_linear_program, nearest_neighbor_tsp, opt_2_opt,
)
from supplymind.core.statistics import (
    detect_outliers_zscore, detect_outliers_iqr,
    bootstrap_confidence_interval, coefficient_of_variation,
)
from supplymind.core.classification import (
    abc_analysis, xyz_classification, abc_xyz_matrix,
)


# ── Timeseries Tests ──

class TestMovingAverage:
    def test_basic(self):
        result = moving_average([1, 2, 3, 4, 5], window=3)
        assert len(result) == 3
        assert abs(result[0] - 2.0) < 0.01

    def test_single_value(self):
        result = moving_average([42], window=1)
        assert len(result) == 1
        assert abs(result[0] - 42) < 0.01


class TestEMA:
    def test_basic(self):
        result = exponential_moving_average([1, 2, 3, 4, 5])
        assert len(result) == 5
        # EMA should be between min and max
        assert min(result) >= 1
        assert max(result) <= 5


class TestHoltWinters:
    def test_forecast_length(self):
        data = [100 + i * 0.5 + 10 * (i % 7 == 6) for i in range(60)]
        result = holt_winters(data, horizon=14)
        assert len(result.predicted) == 14
        assert len(result.lower) == 14
        assert len(result.upper) == 14

    def test_confidence_score_range(self):
        data = list(range(30, 90))
        result = holt_winters(data, horizon=7)
        assert 0 <= result.confidence_score <= 1


class TestSTLDecompose:
    def test_decomposition_lengths(self):
        data = [50 + 20 * (i % 7 < 5) + np.random.randn() * 3 for i in range(56)]
        result = stl_decompose(data, period=7)
        assert len(result.trend) == len(data)
        assert len(result.seasonal) == len(data)
        assert len(result.residual) == len(data)

    def test_reconstruction(self):
        data = [100 + i for i in range(28)]
        result = stl_decompose(data, period=7)
        reconstructed = result.reconstructed
        assert len(reconstructed) > 0


class TestCroston:
    def test_intermittent_data(self):
        data = [10, 0, 0, 15, 0, 8, 0, 0, 12, 0, 0, 9, 0, 18, 0]
        result = croston_forecast(data, horizon=7)
        assert len(result.predicted) == 7
        assert all(p >= 0 for p in result.predicted)

    def test_all_zeros(self):
        result = croston_forecast([0, 0, 0, 0], horizon=5)
        assert result.predicted == [0.0] * 5


class TestAutoForecast:
    def test_auto_selects_method(self):
        data = [100 + i * 0.5 for i in range(60)]
        result = auto_forecast(data, horizon=7)
        assert len(result.predicted) == 7
        assert result.method_used != "unknown"


# ── Inventory Model Tests ──

class TestEOQ:
    def test_basic_eoq(self):
        result = eoq(demand_rate=10000, order_cost=50, holding_cost_per_unit_per_year=2)
        assert result.eoq > 0
        assert result.total_annual_cost > 0

    def test_zero_demand(self):
        result = eoq(0, 50, 2)
        assert result.eoq == 0


class TestROP:
    def test_basic_rop(self):
        result = rop(daily_demand_mean=50, lead_time_days=7, safety_stock=100)
        assert result.rop == 450  # 50*7 + 100
        assert result.safety_stock == 100


class TestSafetyStock:
    def test_service_level_ss(self):
        result = ss_service_level_full(
            demand_mean_daily=100, std_demand_daily=20,
            lead_time_mean_days=7, std_lead_time_days=1,
            target_service_level=0.95,
        )
        assert result.safety_stock >= 0
        assert result.reorder_point > 700  # at least mean demand during LT


class TestNewsvendor:
    def test_optimal_quantity(self):
        result = newsvendor_optimal_order(
            selling_price=35, cost=20, salvage_value=5,
            demand_mean=100, demand_std=25,
        )
        assert result.optimal_quantity > 0
        assert 0 <= result.critical_ratio <= 1


class TestSSPolicySimulation:
    def test_simulation_runs(self):
        demands = [40 + int(np.random.randn() * 8) for _ in range(90)]
        result = s_S_policy_simulation(
            demands=demands, s=200, S=500,
            initial_inventory=300, lead_time=3,
        )
        assert 0 <= result.service_level <= 1
        assert 0 <= result.fill_rate <= 1
        assert result.total_cost >= 0


# ── Optimization Tests ──

class TestAllocationLP:
    def test_simple_allocation(self):
        supplies = {"DC1": 500, "DC2": 300}
        demands = {"StoreA": 400, "StoreB": 250, "StoreC": 150}
        result = allocate_linear_program(supplies, demands)
        assert result.status in ("optimal", "greedy_fallback")
        total_allocated = sum(v for v in result.allocations.values())
        assert total_allocated <= supplies["DC1"] + supplies["DC2"]


class TestTSP:
    def test_nearest_neighbor(self):
        locations = [(0, 0), (1, 0), (1, 1), (0, 1)]
        result = nearest_neighbor_tsp(locations)
        assert len(result.route) == 4
        assert result.total_distance > 0

    def test_2opt_improves(self):
        np.random.seed(42)
        points = [(np.random.rand(), np.random.rand()) for _ in range(15)]
        nn_result = nearest_neighbor_tsp(points)
        opt_result = opt_2_opt(points, initial_route=nn_result.route)
        assert opt_result.total_distance <= nn_result.total_distance + 0.01


# ── Statistics Tests ──

class TestOutlierDetection:
    def test_zscore_no_outliers(self):
        data = [10, 11, 12, 10, 11, 12, 10, 11]
        result = detect_outliers_zscore(data, threshold=3)
        assert len(result.outlier_indices) == 0

    def test_zscore_with_outlier(self):
        data = [10, 11, 10, 11, 10, 11, 1000, 10]
        result = detect_outliers_zscore(data, threshold=2)
        assert len(result.outlier_indices) > 0

    def test_iqr_outliers(self):
        data = [10, 11, 10, 12, 11, 10, 11, 10, 12, 11, 10000]
        result = detect_outliers_iqr(data)
        assert len(result.outlier_indices) >= 1
        assert 10000 in result.outlier_values or result.outlier_indices[-1] == len(data) - 1


class TestBootstrapCI:
    def test_bootstrap_ci(self):
        data = list(range(10, 110))  # 10 to 109
        result = bootstrap_confidence_interval(data, n_samples=500)
        assert result.ci_lower < result.mean < result.ci_upper
        assert result.n_samples == 500


class TestCV:
    def test_cv_constant(self):
        assert coefficient_of_variation([5, 5, 5, 5]) == 0.0

    def test_cv_positive(self):
        cv = coefficient_of_variation([1, 2, 3, 4, 5])
        assert cv > 0


# ── Classification Tests ──

class TestABCAnalysis:
    def test_basic_abc(self):
        items = [
            {"item_id": "A", "value": 800},
            {"item_id": "B", "value": 150},
            {"item_id": "C", "value": 30},
            {"item_id": "D", "value": 15},
            {"item_id": "E", "value": 5},
        ]
        result = abc_analysis(items)
        assert "A" in result.class_a or "B" in result.class_a
        assert len(result.class_a) + len(result.class_b) + len(result.class_c) == 5


class TestXYZClassification:
    def test_stable_is_x(self):
        items = [{"item_id": "S1", "values": [100, 102, 98, 101, 99]}]
        result = xyz_classification(items)
        assert result.class_x == ["S1"]

    def test_volatile_is_z(self):
        items = [{"item_id": "V1", "values": [1, 100, 5, 200, 2, 150]}]
        result = xyz_classification(items)
        assert result.class_z == ["V1"]


class TestABCXYZMatrix:
    def test_matrix_creation(self):
        items = [
            {"item_id": "AX1", "revenue": 800, "demand_values": [100]*30},
            {"item_id": "AZ1", "revenue": 600, "demand_values": [1, 100, 5, 200]},
            {"item_id": "CZ1", "revenue": 10, "demand_values": [1, 200, 3, 500]},
        ]
        result = abc_xyz_matrix(items)
        assert "AX" in result.matrix
        assert isinstance(result.summary, dict)
        assert "total_items" in result.summary
