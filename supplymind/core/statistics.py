"""
Core statistical utilities.

Implements: outlier detection (Z-score, IQR), bootstrap confidence intervals,
coefficient of variation, and other statistical helpers.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class OutlierResult:
    """Result of outlier detection."""
    outlier_indices: list[int]
    outlier_values: list[float]
    cleaned_values: list[float]
    method: str
    threshold: float


@dataclass
class BootstrapResult:
    """Result of bootstrap analysis."""
    mean: float
    std_error: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    n_samples: int


# ──────────────────────────────────────────────
# Z-Score Outlier Detection
# ──────────────────────────────────────────────

def detect_outliers_zscore(
    values: list[float] | np.ndarray,
    threshold: float = 3.0,
) -> OutlierResult:
    """Detect outliers using the Z-score method.

    Values with |z| > threshold are flagged as outliers.
    Z = (x - mean) / std

    Args:
        values: Input data
        threshold: Z-score threshold (default 3.0 = ~99.7% for normal)

    Returns:
        OutlierResult with indices and cleaned data
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < 2:
        return OutlierResult(
            outlier_indices=[],
            outlier_values=[],
            cleaned_values=[float(x) for x in arr],
            method="zscore",
            threshold=threshold,
        )

    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))

    if std_val < 1e-10:
        # All values are identical — no outliers
        return OutlierResult(
            outlier_indices=[],
            outlier_values=[],
            cleaned_values=[float(x) for x in arr],
            method="zscore",
            threshold=threshold,
        )

    z_scores = np.abs((arr - mean_val) / std_val)
    outlier_mask = z_scores > threshold

    outlier_indices = [int(i) for i in range(n) if outlier_mask[i]]
    outlier_values = [float(arr[i]) for i in outlier_indices]
    cleaned_values = [float(arr[i]) for i in range(n) if not outlier_mask[i]]

    return OutlierResult(
        outlier_indices=outlier_indices,
        outlier_values=outlier_values,
        cleaned_values=cleaned_values,
        method="zscore",
        threshold=threshold,
    )


# ──────────────────────────────────────────────
# IQR Outlier Detection
# ──────────────────────────────────────────────

def detect_outliers_iqr(
    values: list[float] | np.ndarray,
    k: float = 1.5,
) -> OutlierResult:
    """Detect outliers using the Interquartile Range (IQR) method.

    Outliers are below Q1 - k*IQR or above Q3 + k*IQR.
    Default k=1.5 is conventional; k=3.0 for "extreme" outliers.

    Args:
        values: Input data
        k: IQR multiplier (default 1.5)

    Returns:
        OutlierResult
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < 4:
        return OutlierResult(
            outlier_indices=[],
            outlier_values=[],
            cleaned_values=[float(x) for x in arr],
            method="iqr",
            threshold=k,
        )

    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    if iqr < 1e-10:
        return OutlierResult(
            outlier_indices=[],
            outlier_values=[],
            cleaned_values=[float(x) for x in arr],
            method="iqr",
            threshold=k,
        )

    lower_bound = q1 - k * iqr
    upper_bound = q3 + k * iqr

    outlier_mask = (arr < lower_bound) | (arr > upper_bound)

    outlier_indices = [int(i) for i in range(n) if outlier_mask[i]]
    outlier_values = [float(arr[i]) for i in outlier_indices]
    cleaned_values = [float(arr[i]) for i in range(n) if not outlier_mask[i]]

    return OutlierResult(
        outlier_indices=outlier_indices,
        outlier_values=outlier_values,
        cleaned_values=cleaned_values,
        method="iqr",
        threshold=k,
    )


# ──────────────────────────────────────────────
# Bootstrap Confidence Interval
# ──────────────────────────────────────────────

def bootstrap_confidence_interval(
    values: list[float] | np.ndarray,
    n_samples: int = 1000,
    confidence_level: float = 0.95,
    statistic: str = "mean",
    rng: random.Random | None = None,
) -> BootstrapResult:
    """Compute bootstrap confidence interval for a statistic.

    Resamples the data with replacement n_samples times to estimate
    the sampling distribution of a statistic.

    Args:
        values: Input data
        n_samples: Number of bootstrap resamples
        confidence_level: Confidence level (e.g., 0.95 for 95% CI)
        statistic: Which statistic to bootstrap ('mean', 'median', 'std')
        rng: Random number generator for reproducibility

    Returns:
        BootstrapResult with CI bounds
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if rng is None:
        rng = random.Random(42)

    # Compute observed statistic
    obs_stat = _compute_statistic(arr, statistic)

    # Bootstrap resampling
    boot_stats = []
    for _ in range(n_samples):
        sample_idx = [rng.randint(0, n - 1) for _ in range(n)]
        sample = arr[sample_idx]
        stat = _compute_statistic(sample, statistic)
        boot_stats.append(stat)

    boot_stats.sort()
    alpha = 1 - confidence_level
    lower_idx = int((alpha / 2) * n_samples)
    upper_idx = int((1 - alpha / 2) * n_samples) - 1

    se = float(np.std(boot_stats)) if n_samples > 1 else 0.0

    return BootstrapResult(
        mean=float(np.mean(boot_stats)),
        std_error=se,
        ci_lower=boot_stats[max(0, lower_idx)],
        ci_upper=boot_stats[min(n_samples - 1, upper_idx)],
        confidence_level=confidence_level,
        n_samples=n_samples,
    )


def _compute_statistic(arr: np.ndarray, statistic: str) -> float:
    """Compute a named statistic on an array."""
    if statistic == "median":
        return float(np.median(arr))
    elif statistic == "std":
        return float(np.std(arr))
    elif statistic == "variance":
        return float(np.var(arr))
    else:  # default: mean
        return float(np.mean(arr))


# ──────────────────────────────────────────────
# Coefficient of Variation
# ──────────────────────────────────────────────

def coefficient_of_variation(values: list[float] | np.ndarray) -> float:
    """Calculate Coefficient of Variation (CV).

    CV = std / mean — measures relative variability.
    Useful for XYZ classification and demand predictability assessment.

    Convention:
      CV < 0.5 → X (stable)
      0.5 ≤ CV < 1.0 → Y (moderate)
      CV ≥ 1.0 → Z (volatile/erratic)

    Args:
        values: Input data

    Returns:
        CV value (non-negative)
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n == 0:
        return 0.0

    mean_val = float(np.mean(arr))
    if abs(mean_val) < 1e-10:
        return 0.0 if n <= 1 else float(np.std(arr))  # Degenerate case

    return float(np.std(arr) / abs(mean_val))


# ──────────────────────────────────────────────
# Additional Statistical Helpers
# ──────────────────────────────────────────────

def summary_statistics(values: list[float] | np.ndarray) -> dict:
    """Compute comprehensive summary statistics.

    Returns dict with count, mean, std, min, max, median,
    q1, q3, iqr, cv, skewness approximation.
    """
    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n == 0:
        return {
            "count": 0, "mean": 0, "std": 0, "min": 0, "max": 0,
            "median": 0, "q1": 0, "q3": 0, "iqr": 0, "cv": 0,
        }

    sorted_arr = np.sort(arr)
    return {
        "count": n,
        "mean": round(float(np.mean(arr)), 4),
        "std": round(float(np.std(arr)), 4),
        "min": round(float(sorted_arr[0]), 4),
        "max": round(float(sorted_arr[-1]), 4),
        "median": round(float(np.median(arr)), 4),
        "q1": round(float(np.percentile(arr, 25)), 4),
        "q3": round(float(np.percentile(arr, 75)), 4),
        "iqr": round(float(np.percentile(arr, 75)) - float(np.percentile(arr, 25)), 4),
        "cv": round(coefficient_of_variation(arr), 4),
    }


def detect_anomalies_moving_avg(
    values: list[float] | np.ndarray,
    window: int = 7,
    threshold_std: float = 2.5,
) -> OutlierResult:
    """Detect anomalies using moving average deviation.

    A point is anomalous if it deviates from its local moving average
    by more than threshold_std local standard deviations.

    More robust than global Z-score for time series with trends.

    Args:
        values: Time series data
        window: Moving average window size
        threshold_std: Number of standard deviations to flag

    Returns:
        OutlierResult
    """
    from supplymind.core.timeseries import moving_average

    arr = np.asarray(values, dtype=float)
    n = len(arr)

    if n < window + 1:
        return detect_outliers_zscore(values, threshold_std)

    ma = np.array(moving_average(arr, window))

    # Align MA with original array (MA is shorter by window-1)
    offset = window // 2
    residuals = np.full(n, np.nan)
    for i in range(offset, n - (window - 1) + offset):
        ma_idx = i - offset
        if ma_idx < len(ma):
            residuals[i] = arr[i] - ma[ma_idx]

    # Compute local std of residuals
    valid_residuals = residuals[~np.isnan(residuals)]
    if len(valid_residuals) < 2:
        return detect_outliers_zscore(values, threshold_std)

    local_std = float(np.std(valid_residuals))
    if local_std < 1e-10:
        return OutlierResult(
            outlier_indices=[], outlier_values=[],
            cleaned_values=[float(x) for x in arr],
            method="moving_avg", threshold=threshold_std,
        )

    outlier_mask = np.zeros(n, dtype=bool)
    for i in range(n):
        if not np.isnan(residuals[i]):
            if abs(residuals[i]) > threshold_std * local_std:
                outlier_mask[i] = True

    outlier_indices = [int(i) for i in range(n) if outlier_mask[i]]
    outlier_values = [float(arr[i]) for i in outlier_indices]
    cleaned_values = [float(arr[i]) for i in range(n) if not outlier_mask[i]]

    return OutlierResult(
        outlier_indices=outlier_indices,
        outlier_values=outlier_values,
        cleaned_values=cleaned_values,
        method="moving_avg",
        threshold=threshold_std,
    )
