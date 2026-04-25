"""
Core time series algorithms — the foundation of demand forecasting.

Implements: Moving Average, EMA, Holt-Winters, STL decomposition, Croston's method.
All algorithms are pure Python/numpy/scipy with no deep learning dependencies.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Result of a forecasting operation.

    Attributes:
        predicted: Point forecasts for each future period
        lower: Lower bound of confidence interval
        upper: Upper bound of confidence interval
        method_used: Name of the method that produced this forecast
        metrics: In-sample fit metrics {mape, mae, rmse}
        confidence_score: Overall confidence (0-1) for HITL decision making
    """

    predicted: list[float]
    lower: list[float] = field(default_factory=list)
    upper: list[float] = field(default_factory=list)
    method_used: str = "unknown"
    metrics: dict = field(default_factory=dict)
    confidence_score: float = 0.8

    def to_dict(self) -> dict:
        return {
            "predicted": self.predicted,
            "lower": self.lower,
            "upper": self.upper,
            "method_used": self.method_used,
            "metrics": self.metrics,
            "confidence_score": self.confidence_score,
        }


@dataclass
class DecompositionResult:
    """Result of time series decomposition.

    Attributes:
        trend: Trend component
        seasonal: Seasonal component
        residual: Residual (remainder) component
        seasonality_strength: How strong seasonality is (0-1)
        period: Detected/used seasonal period
    """

    trend: list[float]
    seasonal: list[float]
    residual: list[float]
    seasonality_strength: float = 0.0
    period: int = 0

    @property
    def reconstructed(self) -> list[float]:
        """Reconstruct original from components."""
        n = min(len(self.trend), len(self.seasonal))
        return [self.trend[i] + self.seasonal[i] for i in range(n)]


# ──────────────────────────────────────────────
# Moving Average
# ──────────────────────────────────────────────

def moving_average(values: list[float] | np.ndarray, window: int = 7) -> list[float]:
    """Simple Moving Average (SMA).

    Args:
        values: Input time series
        window: Smoothing window size

    Returns:
        Smoothed series (length = len(values) - window + 1)
    """
    arr = np.asarray(values, dtype=float)
    if len(arr) < window:
        return [float(np.mean(arr))]
    cumsum = np.cumsum(np.insert(arr, 0, 0))
    result = (cumsum[window:] - cumsum[:-window]) / window
    return [float(x) for x in result]


def exponential_moving_average(
    values: list[float] | np.ndarray,
    alpha: float | None = None,
    window: int | None = None,
) -> list[float]:
    """Exponential Moving Average (EMA).

    Args:
        values: Input time series
        alpha: Smoothing factor (0 < alpha <= 1). If None, derived from window.
        window: Window size to derive alpha (alpha = 2 / (window + 1))

    Returns:
        Smoothed series (same length as input)
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    if n == 0:
        return []

    if alpha is None:
        if window is None:
            window = max(1, n // 10)
        alpha = 2.0 / (window + 1)
    alpha = min(max(alpha, 0.01), 0.99)

    result = np.zeros(n)
    result[0] = arr[0]
    for i in range(1, n):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]

    return [float(x) for x in result]


# ──────────────────────────────────────────────
# Holt-Winters (Triple Exponential Smoothing)
# ──────────────────────────────────────────────

def holt_winters(
    values: list[float] | np.ndarray,
    horizon: int = 14,
    seasonality_periods: int | None = None,
    alpha: float | None = None,
    beta: float | None = None,
    gamma: float | None = None,
    seasonal_type: Literal["additive", "multiplicative"] = "additive",
    confidence_level: float = 0.95,
) -> ForecastResult:
    """Holt-Winters Triple Exponential Smoothing.

    Supports both additive and multiplicative seasonality.
    Auto-detects seasonality if not provided.

    Args:
        values: Historical time series data
        horizon: Number of periods to forecast ahead
        seasonality_periods: Seasonal period (e.g., 7 for weekly, 12 for monthly).
                            If None, auto-detected.
        alpha: Level smoothing factor (auto-optimized if None)
        beta: Trend smoothing factor (auto-optimized if None)
        gamma: Seasonal smoothing factor (auto-optimized if None)
        seasonal_type: 'additive' or 'multiplicative'
        confidence_level: Confidence interval width (default 95%)

    Returns:
        ForecastResult with predictions and confidence intervals
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < 4:
        # Not enough data, fall back to naive/mean
        mean_val = float(np.mean(arr)) if n > 0 else 0.0
        std_val = float(np.std(arr)) if n > 1 else mean_val * 0.2
        z = _z_value(confidence_level)
        return ForecastResult(
            predicted=[mean_val] * horizon,
            lower=[max(0, mean_val - z * std_val)] * horizon,
            upper=[mean_val + z * std_val] * horizon,
            method_used="naive_fallback",
            metrics={"mape": 999.0, "mae": mean_val, "rmse": std_val},
            confidence_score=0.3,
        )

    # Auto-detect seasonality
    if seasonality_periods is None:
        seasonality_periods = _detect_seasonality(arr)

    # If no meaningful seasonality detected, use simple double exponential smoothing
    if seasonality_periods is None or seasonality_periods < 2:
        return _holt_doub_exp(arr, horizon, confidence_level)

    m = seasonality_periods
    if n < 2 * m:
        # Not enough for full seasonal model, fall back to double exp smoothing
        return _holt_doub_exp(arr, horizon, confidence_level)

    # Optimize parameters if not provided
    if alpha is None or beta is None or gamma is None:
        alpha, beta, gamma = _optimize_hw_params(arr, m, seasonal_type)
        logger.info(f"HW optimized params: α={alpha:.3f}, β={beta:.3f}, γ={gamma:.3f}")

    # Initialize components
    if seasonal_type == "additive":
        result = _hw_additive(arr, m, horizon, alpha, beta, gamma, confidence_level)
    else:
        result = _hw_multiplicative(arr, m, horizon, alpha, beta, gamma, confidence_level)

    result.method_used = f"holt_winters_{seasonal_type}"
    return result


def _hw_additive(
    arr: np.ndarray, m: int, horizon: int,
    alpha: float, beta: float, gamma: float, conf_level: float,
) -> ForecastResult:
    """Additive Holt-Winters implementation."""
    n = len(arr)

    # Initialization using averages of first seasons
    n_seasons = n // m
    season_avg = [
        np.mean(arr[i * m:(i + 1) * m]) for i in range(n_seasons)
    ]
    l0 = np.mean(season_avg)
    b0 = (season_avg[-1] - season_avg[0]) / max(n_seasons - 1, 1)

    s0 = np.zeros(m)
    for i in range(m):
        vals = [arr[j * m + i] - season_avg[j] for j in range(n_seasons) if j * m + i < n]
        s0[i] = np.mean(vals) if vals else 0.0

    # Run smoothing
    level = np.zeros(n)
    trend = np.zeros(n)
    seasonal = np.zeros(n + m)  # extra space for indexing convenience

    level[0] = l0
    trend[0] = b0
    seasonal[:m] = s0

    for t in range(1, n):
        level[t] = alpha * (arr[t] - seasonal[t - 1]) + (1 - alpha) * (level[t - 1] + trend[t - 1])
        trend[t] = beta * (level[t] - level[t - 1]) + (1 - beta) * trend[t - 1]
        seasonal[t + m - 1] = gamma * (arr[t] - level[t]) + (1 - gamma) * seasonal[t - 1]

    # Forecast
    predicted = []
    for h in range(1, horizon + 1):
        idx = n - 1 + h
        s_idx = (idx - 1) % m + (m if idx > m else 0)  # proper seasonal index
        # Use last available seasonal value
        s_val = seasonal[n + ((h - 1) % m) - m] if h <= m else seasonal[n - m + (h - 1) % m]
        # Simpler: use the seasonal indices we computed
        fh = level[n - 1] + h * trend[n - 1] + seasonal[n - m + (h - 1) % m]
        predicted.append(float(fh))

    # Confidence intervals
    fitted = np.zeros(n)
    for t in range(n):
        s_idx = t % m
        fitted[t] = level[t] + seasonal[s_idx] if s_idx < len(seasonal) else level[t]
    residuals = arr - fitted
    sigma = float(np.std(residuals)) if n > 1 else 1.0
    z = _z_value(conf_level)

    lower_pred = [max(0, p - z * sigma * math.sqrt(h)) for h, p in enumerate(predicted, 1)]
    upper_pred = [p + z * sigma * math.sqrt(h) for h, p in enumerate(predicted, 1)]

    # Metrics
    mape = _compute_mape(arr, fitted)
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    # Confidence score based on fit quality and data volume
    conf_score = _forecast_confidence(mape, n, horizon)

    return ForecastResult(
        predicted=predicted,
        lower=lower_pred,
        upper=upper_pred,
        metrics={"mape": mape, "mae": mae, "rmse": rmse},
        confidence_score=conf_score,
    )


def _hw_multiplicative(
    arr: np.ndarray, m: int, horizon: int,
    alpha: float, beta: float, gamma: float, conf_level: float,
) -> ForecastResult:
    """Multiplicative Holt-Winters implementation."""
    n = len(arr)

    # Initialize
    n_seasons = n // m
    season_avg = [np.mean(arr[i * m:(i + 1) * m]) for i in range(n_seasons)]
    l0 = np.mean(season_avg)
    b0 = (season_avg[-1] - season_avg[0]) / max(n_seasons - 1, 1)

    s0 = np.ones(m)
    for i in range(m):
        vals = [arr[j * m + i] / season_avg[j] for j in range(n_seasons) if j * m + i < n and season_avg[j] > 0]
        s0[i] = np.mean(vals) if vals else 1.0

    level = np.zeros(n)
    trend = np.zeros(n)
    seasonal = np.zeros(n + m)

    level[0] = l0
    trend[0] = b0
    seasonal[:m] = s0

    for t in range(1, n):
        st_idx = t - 1
        s_val = seasonal[st_idx % m + (m if st_idx >= m else 0)]
        # Use simpler index
        s_val = seasonal[(t - 1) % m] if t <= m else seasonal[t - 1]
        if abs(s_val) < 1e-10:
            s_val = 1.0
        level[t] = alpha * (arr[t] / s_val) + (1 - alpha) * (level[t - 1] + trend[t - 1])
        trend[t] = beta * (level[t] - level[t - 1]) + (1 - beta) * trend[t - 1]
        seasonal[t + m - 1] = gamma * (arr[t] / level[t]) + (1 - gamma) * seasonal[t - 1]

    # Forecast
    predicted = []
    for h in range(1, horizon + 1):
        fh = (level[n - 1] + h * trend[n - 1]) * seasonal[n - m + (h - 1) % m]
        predicted.append(max(0.0, float(fh)))

    # Fitted & residuals
    fitted = np.zeros(n)
    for t in range(n):
        s_val = seasonal[t] if t < len(seasonal) else 1.0
        if abs(s_val) < 1e-10:
            s_val = 1.0
        fitted[t] = (level[t] + trend[t]) * s_val
    residuals = arr - fitted
    sigma = float(np.std(residuals)) if n > 1 else 1.0
    z = _z_value(conf_level)

    lower_pred = [max(0, p - z * sigma * math.sqrt(h)) for h, p in enumerate(predicted, 1)]
    upper_pred = [p + z * sigma * math.sqrt(h) for h, p in enumerate(predicted, 1)]

    mape = _compute_mape(arr, fitted)
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    conf_score = _forecast_confidence(mape, n, horizon)

    return ForecastResult(
        predicted=predicted,
        lower=lower_pred,
        upper=upper_pred,
        metrics={"mape": mape, "mae": mae, "rmse": rmse},
        confidence_score=conf_score,
    )


def _holt_doub_exp(arr: np.ndarray, horizon: int, conf_level: float) -> ForecastResult:
    """Holt's Double Exponential Smoothing (no seasonality)."""
    n = len(arr)
    alpha = 2.0 / (n + 1) if n > 1 else 0.5
    beta = alpha / 10

    level = np.zeros(n)
    trend = np.zeros(n)
    level[0] = arr[0]
    trend[0] = arr[1] - arr[0] if n > 1 else 0.0

    for t in range(1, n):
        level[t] = alpha * arr[t] + (1 - alpha) * (level[t - 1] + trend[t - 1])
        trend[t] = beta * (level[t] - level[t - 1]) + (1 - beta) * trend[t - 1]

    predicted = [float(level[n - 1] + (h + 1) * trend[n - 1]) for h in range(horizon)]

    fitted = level + trend
    residuals = arr - fitted
    sigma = float(np.std(residuals)) if n > 1 else 1.0
    z = _z_value(conf_level)

    lower = [max(0, p - z * sigma * math.sqrt(h + 1)) for h, p in enumerate(predicted)]
    upper = [p + z * sigma * math.sqrt(h + 1) for h, p in enumerate(predicted)]

    mape = _compute_mape(arr, fitted)
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    return ForecastResult(
        predicted=predicted,
        lower=lower,
        upper=upper,
        method_used="holt_double",
        metrics={"mape": mape, "mae": mae, "rmse": rmse},
        confidence_score=_forecast_confidence(mape, n, horizon),
    )


# ──────────────────────────────────────────────
# STL-like Decomposition (simplified)
# ──────────────────────────────────────────────

def stl_decompose(
    values: list[float] | np.ndarray,
    period: int | None = None,
) -> DecompositionResult:
    """Simplified Season-Trend decomposition using LOESS-like approach.

    This is a simplified STL that uses MA-based smoothing rather than full LOESS.
    It provides good results for most supply chain use cases.

    Args:
        values: Time series data
        period: Seasonal period. If None, auto-detected.

    Returns:
        DecompositionResult with trend, seasonal, and residual components
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < 4:
        return DecompositionResult(
            trend=list(arr),
            seasonal=[0.0] * n,
            residual=[0.0] * n,
            seasonality_strength=0.0,
            period=period or 1,
        )

    # Auto-detect period
    if period is None:
        period = _detect_seasonality(arr) or 1

    if period < 2 or n < 2 * period:
        # No clear seasonality, just extract trend
        trend = _smooth_trend(arr, max(3, n // 10))
        residual = arr - trend
        return DecompositionResult(
            trend=[float(x) for x in trend],
            seasonal=[0.0] * n,
            residual=[float(x) for x in residual],
            seasonality_strength=0.0,
            period=period,
        )

    # Step 1: Extract trend (moving average with window = period)
    trend = _smooth_trend(arr, period)

    # Step 2: Detrend
    detrended = arr - trend

    # Step 3: Estimate seasonal component by averaging each seasonal position
    seasonal_raw = np.zeros(n)
    for i in range(period):
        indices = list(range(i, n, period))
        if indices:
            seasonal_mean = np.mean(detrended[indices])
            for idx in indices:
                seasonal_raw[idx] = seasonal_mean

    # Normalize seasonal component (should sum to ~0 over one period)
    seasonal_mean_over_period = np.mean(seasonal_raw[:period * (n // period)])
    seasonal = seasonal_raw - seasonal_mean_over_period

    # Step 4: Residual
    residual = arr - trend - seasonal

    # Seasonality strength: var(seasonal) / var(seasonal + residual)
    total_var = np.var(seasonal) + np.var(residual)
    strength = float(np.var(seasonal) / total_var) if total_var > 0 else 0.0

    return DecompositionResult(
        trend=[float(x) for x in trend],
        seasonal=[float(x) for x in seasonal],
        residual=[float(x) for x in residual],
        seasonality_strength=min(1.0, strength),
        period=period,
    )


def _smooth_trend(arr: np.ndarray, window: int) -> np.ndarray:
    """Apply centered moving average for trend extraction."""
    n = len(arr)
    half_w = window // 2
    trend = np.zeros(n)

    for i in range(n):
        start = max(0, i - half_w)
        end = min(n, i + half_w + 1)
        trend[i] = np.mean(arr[start:end])

    return trend


# ──────────────────────────────────────────────
# Croston's Method for Intermittent Demand
# ──────────────────────────────────────────────

def croston_forecast(
    values: list[float] | np.ndarray,
    horizon: int = 14,
    variant: Literal["classic", "sba", "tsb"] = "sba",
    alpha: float = 0.2,
    confidence_level: float = 0.95,
) -> ForecastResult:
    """Croston's method for intermittent/sporadic demand forecasting.

    Variants:
    - classic: Original Croston (1972) — tends to be biased upward
    - sba: Syntetos-Boylan Approximation (2001) — reduces bias
    - tsb: Teunter-Syntet-Babai (2010) — further improved

    Args:
        values: Demand history (may contain many zeros)
        horizon: Forecast horizon
        variant: Which variant to use
        alpha: Smoothing parameter
        confidence_level: For prediction intervals

    Returns:
        ForecastResult
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n == 0:
        return ForecastResult(
            predicted=[0.0] * horizon,
            method_used=f"croston_{variant}",
            metrics={"mape": 999.0, "mae": 0.0, "rmse": 0.0},
            confidence_score=0.1,
        )

    # Find non-zero demand intervals
    demands: list[float] = []
    intervals: list[int] = []

    prev_nonzero = -1
    for i, v in enumerate(arr):
        if v > 0:
            demands.append(v)
            if prev_nonzero >= 0:
                intervals.append(i - prev_nonzero)
            elif i > 0:
                # First non-zero: use its position as first interval estimate
                intervals.append(i + 1)
            prev_nonzero = i

    if not demands:
        # All zeros
        return ForecastResult(
            predicted=[0.0] * horizon,
            method_used=f"croston_{variant}",
            metrics={"mape": 0.0, "mae": 0.0, "rmse": 0.0},
            confidence_score=0.9,
        )

    # Apply exponential smoothing to demand sizes and intervals
    d_smooth = demands[0]
    p_smooth = intervals[0] if intervals else 1.0

    di = 1  # demand index
    ii = 0  # interval index
    for i in range(1, n):
        if arr[i] > 0 and di < len(demands):
            d_smooth = alpha * demands[di] + (1 - alpha) * d_smooth
            di += 1
            if ii < len(intervals):
                p_smooth = alpha * intervals[ii] + (1 - alpha) * p_smooth
                ii += 1

    # Ensure we've processed all
    while di < len(demands):
        d_smooth = alpha * demands[di] + (1 - alpha) * d_smooth
        di += 1
    while ii < len(intervals):
        p_smooth = alpha * intervals[ii] + (1 - alpha) * p_smooth
        ii += 1

    p_smooth = max(p_smooth, 1.0)  # Avoid division by zero

    # Compute forecast based on variant
    if variant == "classic":
        forecast_value = d_smooth / p_smooth
    elif variant == "sba":
        # SBA correction factor
        forecast_value = (1 - alpha / 2) * d_smooth / p_smooth
    else:  # tsb
        # TSB: separate smoothing of demand probability
        prob = 1.0 / p_smooth
        forecast_value = d_smooth * prob

    forecast_value = max(0.0, forecast_value)
    predicted = [forecast_value] * horizon

    # Simple confidence intervals for intermittent demand
    sigma = forecast_value * 0.5  # High uncertainty for intermittent
    z = _z_value(confidence_level)
    lower = [max(0.0, forecast_value - z * sigma)] * horizon
    upper = [forecast_value + z * sigma] * horizon

    # Metrics (in-sample is tricky for Croston; use approximate)
    nonzero_arr = arr[arr > 0]
    if len(nonzero_arr) > 0:
        mae = float(np.mean(np.abs(nonzero_arr - d_smooth))) if d_smooth > 0 else float(np.mean(nonzero_arr))
        mape = _compute_mape(nonzero_arr, [d_smooth] * len(nonzero_arr))
    else:
        mae = 0.0
        mape = 0.0

    # Low confidence for intermittent (inherently uncertain)
    nonzero_ratio = len(demands) / n if n > 0 else 0
    conf_score = max(0.3, min(0.85, 1.0 - nonzero_ratio * 0.5))

    return ForecastResult(
        predicted=predicted,
        lower=lower,
        upper=upper,
        method_used=f"croston_{variant}",
        metrics={"mape": mape, "mae": mae, "rmse": math.sqrt(mae)},
        confidence_score=conf_score,
    )


# ──────────────────────────────────────────────
# Auto Method Selection
# ──────────────────────────────────────────────

def auto_forecast(
    values: list[float] | np.ndarray,
    horizon: int = 14,
    confidence_level: float = 0.95,
) -> ForecastResult:
    """Automatically select the best forecasting method.

    Selection logic:
    1. Check if data is intermittent (>50% zeros) → Croston
    2. Check for strong seasonality → Holt-Winters
    3. Check for trend presence → Double Exponential Smoothing
    4. Default → EMA / Moving Average

    Args:
        values: Historical data
        horizon: Forecast horizon
        confidence_level: Confidence interval width

    Returns:
        ForecastResult from the selected method
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < 4:
        mean_val = float(np.mean(arr)) if n > 0 else 0.0
        return ForecastResult(
            predicted=[mean_val] * horizon,
            method_used="auto_naive",
            metrics={"mape": 999.0},
            confidence_score=0.2,
        )

    # Check intermittency
    zero_ratio = np.sum(arr == 0) / n
    if zero_ratio > 0.5:
        logger.info("Auto-select: Croston (intermittent demand, %.0f%% zeros)", zero_ratio * 100)
        return croston_forecast(arr, horizon, confidence_level=confidence_level)

    # Detect seasonality
    period = _detect_seasonality(arr)
    has_strong_seasonality = False
    if period and period >= 2:
        decomp = stl_decompose(arr, period)
        has_strong_seasonality = decomp.seasonality_strength > 0.3

    if has_strong_seasonality:
        logger.info("Auto-select: Holt-Winters (seasonality detected, period=%d)", period)
        return holt_winters(arr, horizon, seasonality_periods=period, confidence_level=confidence_level)

    # Check for trend
    first_half = arr[:n // 2]
    second_half = arr[n // 2:]
    if len(first_half) > 2 and len(second_half) > 2:
        trend_slope = np.mean(second_half) - np.mean(first_half)
        rel_trend = abs(trend_slope) / (np.mean(arr) + 1e-6)
        if rel_trend > 0.1:
            logger.info("Auto-select: Holt double exp smoothing (trend detected)")
            return _holt_doub_exp(arr, horizon, confidence_level)

    # Default: EMA
    logger.info("Auto-select: EMA (stable pattern)")
    ema_result = exponential_moving_average(arr)
    last_ema = ema_result[-1] if ema_result else float(np.mean(arr))

    sigma = float(np.std(arr)) if n > 1 else last_ema * 0.2
    z = _z_value(confidence_level)
    predicted = [last_ema] * horizon
    lower = [max(0, last_ema - z * sigma)] * horizon
    upper = [last_ema + z * sigma] * horizon

    mae = float(np.mean(np.abs(arr - np.array(ema_result))))
    mape = _compute_mape(arr, np.array(ema_result))

    return ForecastResult(
        predicted=predicted,
        lower=lower,
        upper=upper,
        method_used="ema",
        metrics={"mape": mape, "mae": mae, "rmse": float(np.sqrt(np.mean((arr - np.array(ema_result))**2)))},
        confidence_score=_forecast_confidence(mape, n, horizon),
    )


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────

def _detect_seasonality(arr: np.ndarray) -> int | None:
    """Detect the dominant seasonal period using autocorrelation.

    Checks common periods: 7 (weekly), 30 (monthly), 12, 4 (quarterly), etc.
    """
    n = len(arr)
    if n < 8:
        return None

    # Mean-center
    arr_centered = arr - np.mean(arr)
    variance = np.var(arr_centered)
    if variance < 1e-10:
        return None

    # Test candidate periods
    candidates = [7, 12, 4, 30, 24, 52, 3, 6, 5, 10]
    # Filter to reasonable candidates given data length
    candidates = [p for p in candidates if 2 * p <= n and p < n // 2]

    if not candidates:
        return None

    best_period = None
    best_acf = 0.0

    for period in candidates:
        # Compute autocorrelation at this lag
        acf_values = []
        for lag in [period]:
            if lag >= n:
                continue
            c = np.cov(arr_centered[:-lag], arr_centered[lag:])[0, 1] if lag > 0 else variance
            acf = c / variance if variance > 0 else 0
            acf_values.append(abs(acf))

        avg_acf = np.mean(acf_values) if acf_values else 0
        if avg_acf > best_acf:
            best_acf = avg_acf
            best_period = period

    # Only return if ACF is significant enough
    threshold = 1.96 / math.sqrt(n)  # Approximate significance threshold
    if best_acf > threshold:
        return best_period
    return None


def _optimize_hw_params(
    arr: np.ndarray, m: int, seasonal_type: str,
) -> tuple[float, float, float]:
    """Simple grid search for optimal HW parameters."""
    best_mape = float('inf')
    best_params = (0.2, 0.1, 0.1)

    alphas = [0.1, 0.2, 0.3, 0.4, 0.5]
    betas = [0.05, 0.1, 0.15, 0.2]
    gammas = [0.05, 0.1, 0.15, 0.2]

    for alpha in alphas:
        for beta in betas:
            for gamma in gammas:
                try:
                    if seasonal_type == "additive":
                        result = _hw_additive(arr, m, 1, alpha, beta, gamma, 0.95)
                    else:
                        result = _hw_multiplicative(arr, m, 1, alpha, beta, gamma, 0.95)
                    if result.metrics.get("mape", 999) < best_mape:
                        best_mape = result.metrics["mape"]
                        best_params = (alpha, beta, gamma)
                except Exception:
                    continue

    return best_params


def _z_value(confidence_level: float) -> float:
    """Get Z-value for confidence level (normal distribution)."""
    return abs(stats.norm.ppf((1 - confidence_level) / 2))


def _compute_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Mean Absolute Percentage Error."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = actual != 0
    if not np.any(mask):
        return 0.0
    errors = np.abs((actual[mask] - predicted[mask]) / actual[mask])
    return float(np.mean(errors) * 100)


def _forecast_confidence(mape: float, n_data: int, horizon: int) -> float:
    """Estimate overall forecast confidence score (0-1).

    Combines:
    - Fit quality (inverse of MAPE)
    - Data volume (more data = more confident)
    - Horizon penalty (longer horizon = less confident)
    """
    # Fit quality component (0-0.5)
    fit_conf = max(0, 0.5 - mape / 100)

    # Data volume component (0-0.3)
    if n_data >= 180:
        vol_conf = 0.3
    elif n_data >= 90:
        vol_conf = 0.25
    elif n_data >= 30:
        vol_conf = 0.15
    else:
        vol_conf = 0.05

    # Horizon penalty (0-0.2)
    horizon_penalty = max(0, 0.2 * (1 - horizon / 60))

    return min(1.0, max(0.1, fit_conf + vol_conf + horizon_penalty))
