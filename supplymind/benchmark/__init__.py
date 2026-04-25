"""
Benchmark Suite — compare SupplyMind skills against industry baselines.

Provides naive/seasonal-naive baselines and MAPE/RMSE/MAE metrics
for evaluating forecast accuracy on real or synthetic datasets.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    method: str
    mape: float
    rmse: float
    mae: float
    duration_ms: float
    horizon: int
    n_series: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report across methods."""
    dataset_id: str
    results: list[BenchmarkResult] = field(default_factory=list)
    best_method: str = ""
    best_mape: float = float("inf")

    def summary(self) -> dict[str, Any]:
        rows = []
        for r in sorted(self.results, key=lambda x: x.mape):
            rows.append({
                "method": r.method,
                "mape": round(r.mape, 2),
                "rmse": round(r.rmse, 2),
                "mae": round(r.mae, 2),
                "duration_ms": round(r.duration_ms, 1),
            })
        return {
            "dataset": self.dataset_id,
            "best_method": self.best_method,
            "best_mape": round(self.best_mape, 2),
            "results": rows,
        }


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _naive_forecast(train: np.ndarray, horizon: int) -> np.ndarray:
    """Repeat last value."""
    return np.full(horizon, train[-1])


def _seasonal_naive_forecast(train: np.ndarray, horizon: int, period: int = 7) -> np.ndarray:
    """Repeat last season."""
    season = train[-period:]
    reps = math.ceil(horizon / period)
    return np.tile(season, reps)[:horizon]


def _mean_forecast(train: np.ndarray, horizon: int) -> np.ndarray:
    """Predict the historical mean."""
    return np.full(horizon, np.mean(train))


def _drift_forecast(train: np.ndarray, horizon: int) -> np.ndarray:
    """Linear drift from first to last value."""
    n = len(train)
    if n < 2:
        return np.full(horizon, train[-1])
    slope = (train[-1] - train[0]) / (n - 1)
    return np.array([train[-1] + slope * (i + 1) for i in range(horizon)])


def _supplymind_forecast(train: np.ndarray, horizon: int, method: str = "auto") -> np.ndarray:
    """Run SupplyMind demand forecast."""
    from supplymind.skills.demand.forecast.main import DemandForecast
    skill = DemandForecast()
    result = skill._forecast_single(train, method, horizon, 0.95)
    return np.array(result.predicted[:horizon])


BASELINE_METHODS = {
    "naive": _naive_forecast,
    "seasonal_naive": _seasonal_naive_forecast,
    "mean": _mean_forecast,
    "drift": _drift_forecast,
}

SUPPLYMIND_METHODS = ["auto", "ma", "ema", "holt_winters"]


def run_benchmark(
    dataset_id: str = "retail_grocery",
    horizon: int = 14,
    methods: list[str] | None = None,
) -> BenchmarkReport:
    """Run benchmark comparing SupplyMind methods against baselines.

    Args:
        dataset_id: Dataset to benchmark on
        horizon: Forecast horizon (days)
        methods: Methods to test. Default: all baselines + SupplyMind methods.

    Returns:
        BenchmarkReport with per-method metrics
    """
    from supplymind.datasets import load_dataset

    data = load_dataset(dataset_id)
    if not data.demand_history:
        raise ValueError(f"No demand data in dataset '{dataset_id}'")

    # Group by SKU
    sku_series: dict[str, list[float]] = {}
    for r in sorted(data.demand_history, key=lambda x: (x.sku_id, str(x.demand_date))):
        sku_series.setdefault(r.sku_id, []).append(r.quantity)

    # Filter series long enough for train+test split
    min_len = horizon + 30
    valid_series = {k: np.array(v) for k, v in sku_series.items() if len(v) >= min_len}

    if not valid_series:
        raise ValueError(f"No series with >= {min_len} observations for horizon={horizon}")

    test_methods = methods or (list(BASELINE_METHODS.keys()) + [f"supplymind_{m}" for m in SUPPLYMIND_METHODS])

    report = BenchmarkReport(dataset_id=dataset_id)

    for method_name in test_methods:
        all_mape, all_rmse, all_mae = [], [], []
        t0 = time.time()

        for sku_id, series in valid_series.items():
            train = series[:-horizon]
            actual = series[-horizon:]

            try:
                if method_name in BASELINE_METHODS:
                    predicted = BASELINE_METHODS[method_name](train, horizon)
                elif method_name.startswith("supplymind_"):
                    sm_method = method_name.replace("supplymind_", "")
                    predicted = _supplymind_forecast(train, horizon, sm_method)
                else:
                    continue

                predicted = predicted[:len(actual)]
                actual_trimmed = actual[:len(predicted)]

                all_mape.append(_mape(actual_trimmed, predicted))
                all_rmse.append(_rmse(actual_trimmed, predicted))
                all_mae.append(_mae(actual_trimmed, predicted))
            except Exception as e:
                logger.warning(f"Benchmark {method_name} failed on {sku_id}: {e}")

        elapsed = (time.time() - t0) * 1000

        if all_mape:
            result = BenchmarkResult(
                method=method_name,
                mape=float(np.mean(all_mape)),
                rmse=float(np.mean(all_rmse)),
                mae=float(np.mean(all_mae)),
                duration_ms=elapsed,
                horizon=horizon,
                n_series=len(valid_series),
            )
            report.results.append(result)

            if result.mape < report.best_mape:
                report.best_mape = result.mape
                report.best_method = method_name

    return report
