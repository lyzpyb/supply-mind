"""
Backtesting System — automated forecast accuracy evaluation.

Implements rolling-origin evaluation to measure post-mortem forecast accuracy.
Results feed into the Learning Loop for continuous improvement.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np

from supplymind.core.timeseries import (
    moving_average,
    exponential_moving_average,
    holt_winters,
    croston_forecast,
    auto_forecast,
    ForecastResult,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    sku_id: str = ""
    method: str = ""
    horizon: int = 14
    n_folds: int = 0
    mape_scores: list[float] = field(default_factory=list)
    mae_scores: list[float] = field(default_factory=list)
    rmse_scores: list[float] = field(default_factory=list)
    avg_mape: float = 0.0
    avg_mae: float = 0.0
    avg_rmse: float = 0.0
    std_mape: float = 0.0
    best_fold_mape: float = 999.0
    worst_fold_mape: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class BacktestReport:
    """Complete backtest report across methods."""

    results: list[BacktestResult] = field(default_factory=list)
    comparison: dict = field(default_factory=dict)
    recommendation: str = ""
    generated_at: str = ""


class Backtester:
    """Rolling-origin backtesting engine.

    For each fold:
    1. Train on data[0 : train_end]
    2. Forecast horizon steps ahead
    3. Compare with actual values
    4. Move window forward
    """

    def __init__(self):
        pass

    def run_backtest(
        self,
        values: list[float],
        horizon: int = 14,
        methods: list[str] | None = None,
        n_folds: int | None = None,
        min_train_size: int = 30,
        step_size: int | None = None,
        sku_id: str = "",
    ) -> BacktestReport:
        """Run rolling-origin backtest.

        Args:
            values: Full time series (actual values)
            horizon: Forecast horizon per fold
            methods: List of methods to test (default: common set)
            n_folds: Number of folds (default: auto based on data length)
            min_train_size: Minimum training samples before first forecast
            step_size: Steps to move between folds (default: horizon)
            sku_id: SKU identifier for reporting
        """
        arr = np.array(values, dtype=float)
        n = len(arr)

        if n < min_train_size + horizon:
            logger.warning(f"Not enough data for backtest: {n} < {min_train_size + horizon}")
            return BacktestReport(results=[], recommendation="Insufficient data")

        if methods is None:
            methods = ["auto", "ma", "ema", "holt_winters"]

        if n_folds is None:
            n_folds = max(1, (n - min_train_size - horizon) // (step_size or horizon))

        if step_size is None:
            step_size = horizon

        all_results: list[BacktestResult] = []

        for method in methods:
            result = self._backtest_method(arr, method, horizon, n_folds, min_train_size, step_size, sku_id)
            all_results.append(result)

        # Build comparison
        best_method = min(all_results, key=lambda r: r.avg_mape)
        comparison = {
            "methods_tested": len(all_results),
            "ranking_by_mape": sorted(
                [(r.method, r.avg_mape, r.avg_mae) for r in all_results],
                key=lambda x: x[1]
            ),
            "best_method": best_method.method,
            "best_mape": round(best_method.avg_mape, 2),
            "worst_method": max(all_results, key=lambda r: r.avg_mape).method,
            "improvement_over_naive": self._naive_baseline(arr, horizon, min_train_size, best_method),
        }

        rec = f"Best method for {sku_id or 'this SKU'} is '{best_method.method}' "
        rec += f"(MAPE={best_method.avg_mape:.1f}%, std={best_method.std_mape:.1f}%)"

        return BacktestReport(
            results=all_results,
            comparison=comparison,
            recommendation=rec,
            generated_at=date.today().isoformat(),
        )

    def _backtest_method(self, arr: np.ndarray, method: str, horizon: int,
                         n_folds: int, min_train: int, step: int, sku_id: str) -> BacktestResult:
        """Run backtest for one method."""
        n = len(arr)
        mapes = []
        maes = []
        rmses = []

        for fold in range(n_folds):
            train_end = min_train + fold * step
            if train_end + horizon > n:
                break

            train_data = arr[:train_end].tolist()
            actual = arr[train_end:train_end + horizon]

            # Generate forecast
            try:
                fc_result = self._run_method(train_data, method, horizon)
                predicted = np.array(fc_result.predicted[:len(actual)])
            except Exception as e:
                logger.debug(f"Fold {fold} failed for {method}: {e}")
                predicted = np.full(len(actual), np.mean(train_data))

            # Compute metrics
            mape = self._compute_mape(actual, predicted)
            mae = float(np.mean(np.abs(actual - predicted)))
            rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

            mapes.append(mape)
            maes.append(mae)
            rmses.append(rmse)

        return BacktestResult(
            sku_id=sku_id,
            method=method,
            horizon=horizon,
            n_folds=len(mapes),
            mape_scores=[round(m, 2) for m in mapes],
            mae_scores=[round(m, 2) for m in maes],
            rmse_scores=[round(r, 2) for r in rmses],
            avg_mape=round(float(np.mean(mapes)), 2) if mapes else 999,
            avg_mae=round(float(np.mean(maes)), 2) if maes else 0,
            avg_rmse=round(float(np.mean(rmses)), 2) if rmses else 0,
            std_mape=round(float(np.std(mapes)), 2) if mapes else 0,
            best_fold_mape=round(min(mapes), 2) if mapes else 999,
            worst_fold_mape=round(max(mapes), 2) if mapes else 0,
        )

    @staticmethod
    def _run_method(values: list[float], method: str, horizon: int) -> ForecastResult:
        """Run a forecasting method."""
        if method == "auto":
            return auto_forecast(values, horizon)
        elif method == "ma":
            window = min(len(values) // 2, 14) if len(values) > 4 else 7
            smoothed = moving_average(values, window)
            last_val = smoothed[-1] if smoothed else float(np.mean(values))
            sigma = float(np.std(values)) * 0.5
            return ForecastResult(predicted=[last_val] * horizon, method_used="ma", confidence_score=0.6)
        elif method == "ema":
            ema = exponential_moving_average(values)
            last_ema = ema[-1] if ema else float(np.mean(values))
            return ForecastResult(predicted=[last_ema] * horizon, method_used="ema", confidence_score=0.65)
        elif method == "holt_winters":
            return holt_winters(values, horizon)
        elif method == "croston":
            return croston_forecast(values, horizon)
        else:
            return auto_forecast(values, horizon)

    @staticmethod
    def _compute_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
        mask = actual != 0
        if not np.any(mask):
            return 0.0
        errors = np.abs((actual[mask] - predicted[mask]) / actual[mask])
        return float(np.mean(errors) * 100)

    @staticmethod
    def _naive_baseline(arr: np.ndarray, horizon: int, min_train: int, best_result: BacktestResult) -> dict:
        """Compare against naive (last-value) baseline."""
        n = len(arr)
        naive_mapes = []
        step = horizon
        folds = max(1, (n - min_train - horizon) // step)

        for fold in range(folds):
            train_end = min_train + fold * step
            if train_end + horizon > n:
                break
            last_val = arr[train_end - 1]
            actual = arr[train_end:train_end + horizon]
            predicted = np.full(len(actual), last_val)
            mape = Backtester._compute_mape(actual, predicted)
            naive_mapes.append(mape)

        naive_avg = float(np.mean(naive_mapes)) if naive_mapes else 999
        improvement = ((naive_avg - best_result.avg_mape) / naive_avg * 100) if naive_avg > 0 else 0

        return {
            "naive_mape": round(naive_avg, 2),
            "best_method_mape": best_result.avg_mape,
            "improvement_pct": round(improvement, 1),
        }
