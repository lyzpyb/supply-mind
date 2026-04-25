"""Tests for the benchmark suite."""

import numpy as np
import pytest

from supplymind.benchmark import (
    BenchmarkReport,
    BenchmarkResult,
    _mape,
    _rmse,
    _mae,
    _naive_forecast,
    _seasonal_naive_forecast,
    _mean_forecast,
    _drift_forecast,
    run_benchmark,
)


class TestMetrics:
    """Test accuracy metric calculations."""

    def test_mape_basic(self):
        actual = np.array([100.0, 200.0, 150.0])
        predicted = np.array([110.0, 180.0, 160.0])
        result = _mape(actual, predicted)
        assert 5.0 < result < 12.0

    def test_mape_zero_actual_ignored(self):
        actual = np.array([0.0, 100.0, 200.0])
        predicted = np.array([10.0, 110.0, 190.0])
        result = _mape(actual, predicted)
        assert result > 0

    def test_rmse_basic(self):
        actual = np.array([100.0, 200.0])
        predicted = np.array([100.0, 200.0])
        assert _rmse(actual, predicted) == 0.0

    def test_mae_basic(self):
        actual = np.array([100.0, 200.0, 300.0])
        predicted = np.array([110.0, 190.0, 310.0])
        assert _mae(actual, predicted) == 10.0


class TestBaselines:
    """Test baseline forecast methods."""

    def test_naive_repeats_last(self):
        train = np.array([10, 20, 30, 40, 50])
        result = _naive_forecast(train, 3)
        np.testing.assert_array_equal(result, [50, 50, 50])

    def test_seasonal_naive(self):
        train = np.array([1, 2, 3, 4, 5, 6, 7] * 3)
        result = _seasonal_naive_forecast(train, 7, period=7)
        np.testing.assert_array_equal(result, [1, 2, 3, 4, 5, 6, 7])

    def test_mean_forecast(self):
        train = np.array([10, 20, 30])
        result = _mean_forecast(train, 2)
        np.testing.assert_array_equal(result, [20, 20])

    def test_drift_forecast(self):
        train = np.array([10, 20, 30])
        result = _drift_forecast(train, 2)
        assert result[0] == pytest.approx(40.0)
        assert result[1] == pytest.approx(50.0)


class TestBenchmarkRun:
    """Test end-to-end benchmark execution."""

    def test_run_benchmark_retail_grocery(self):
        report = run_benchmark(dataset_id="retail_grocery", horizon=14)
        assert isinstance(report, BenchmarkReport)
        assert len(report.results) > 0
        assert report.best_method != ""
        assert report.best_mape < 100

    def test_benchmark_includes_baselines(self):
        report = run_benchmark(dataset_id="retail_grocery", horizon=14,
                               methods=["naive", "mean"])
        method_names = {r.method for r in report.results}
        assert "naive" in method_names
        assert "mean" in method_names

    def test_benchmark_includes_supplymind(self):
        report = run_benchmark(dataset_id="retail_grocery", horizon=14,
                               methods=["naive", "supplymind_auto"])
        method_names = {r.method for r in report.results}
        assert "supplymind_auto" in method_names

    def test_benchmark_result_has_metrics(self):
        report = run_benchmark(dataset_id="retail_grocery", horizon=14,
                               methods=["naive"])
        r = report.results[0]
        assert r.mape >= 0
        assert r.rmse >= 0
        assert r.mae >= 0
        assert r.duration_ms >= 0
        assert r.horizon == 14

    def test_benchmark_summary(self):
        report = run_benchmark(dataset_id="retail_grocery", horizon=14,
                               methods=["naive", "mean"])
        summary = report.summary()
        assert "dataset" in summary
        assert "best_method" in summary
        assert "results" in summary
        assert len(summary["results"]) == 2
