"""Core algorithm engine — pure Python, no framework dependencies."""

from supplymind.core.timeseries import (
    moving_average,
    exponential_moving_average,
    holt_winters,
    stl_decompose,
    croston_forecast,
    ForecastResult,
    DecompositionResult,
)
from supplymind.core.inventory_models import (
    eoq,
    rop,
    ss_service_level,
    ss_stochastic,
    newsvendor_optimal_order,
    s_S_policy_simulation,
)
from supplymind.core.optimization import (
    allocate_linear_program,
    nearest_neighbor_tsp,
    opt_2_opt,
)
from supplymind.core.statistics import (
    detect_outliers_zscore,
    detect_outliers_iqr,
    bootstrap_confidence_interval,
    coefficient_of_variation,
)
from supplymind.core.classification import (
    abc_analysis,
    xyz_classification,
    abc_xyz_matrix,
)

__all__ = [
    # Timeseries
    "moving_average",
    "exponential_moving_average",
    "holt_winters",
    "stl_decompose",
    "croston_forecast",
    "ForecastResult",
    "DecompositionResult",
    # Inventory
    "eoq",
    "rop",
    "ss_service_level",
    "ss_stochastic",
    "newsvendor_optimal_order",
    "s_S_policy_simulation",
    # Optimization
    "allocate_linear_program",
    "nearest_neighbor_tsp",
    "opt_2_opt",
    # Statistics
    "detect_outliers_zscore",
    "detect_outliers_iqr",
    "bootstrap_confidence_interval",
    "coefficient_of_variation",
    # Classification
    "abc_analysis",
    "xyz_classification",
    "abc_xyz_matrix",
]
