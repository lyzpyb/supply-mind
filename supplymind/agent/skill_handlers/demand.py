"""
Demand Skill Handlers — async bridges for all demand-related skills.

Covers: forecast, decompose, anomaly, newproduct, intermittent, reconcile
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Demand Forecast ───────────────────────────────────────────────────────

DEMAND_FORECAST_TOOL_SPEC = {
    "name": "demand_forecast",
    "description": (
        "Generate demand forecasts with confidence intervals for supply chain planning.\n\n"
        "The PRIMARY forecasting tool for supply chain operations:\n"
        "- Supports multiple methods: auto (recommended), ma, ema, holt_winters, croston\n"
        "- Auto method selects the best algorithm per-SKU based on data characteristics\n"
        "- Provides 95% confidence intervals (configurable) for risk assessment\n"
        "- Handles multiple SKUs and locations in a single call\n\n"
        "REQUIRED before any inventory or fulfillment planning step.\n"
        "Output includes per-SKU daily forecasts with upper/lower bounds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "demand_history": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Historical demand records. Each record: "
                    "{sku_id, quantity, date (YYYY-MM-DD), location_id?, sku_name?}"
                ),
            },
            "horizon": {
                "type": "integer",
                "default": 14,
                "description": "Forecast horizon in days (1-365, default: 14)",
            },
            "method": {
                "type": "string",
                "enum": ["auto", "ma", "ema", "holt_winters", "croston"],
                "default": "auto",
                "description": (
                    "Forecasting method. 'auto' picks the best method per-SKU. "
                    "'croston' for intermittent demand, 'holt_winters' for seasonal data."
                ),
            },
            "confidence_level": {
                "type": "number",
                "default": 0.95,
                "description": "Confidence interval level (0.8-0.99, default: 0.95)",
            },
            "sku_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of SKU IDs to forecast (default: all)",
            },
            "location_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of location IDs to include",
            },
        },
        "required": ["demand_history"],
    },
}


async def demand_forecast_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for demand forecast tool."""
    try:
        from supplymind.skills.demand.forecast.main import DemandForecast
        from supplymind.skills.demand.forecast.schema import ForecastInput

        input_data = ForecastInput(
            demand_history=arguments["demand_history"],
            horizon=arguments.get("horizon", 14),
            method=arguments.get("method", "auto"),
            confidence_level=arguments.get("confidence_level", 0.95),
            sku_filter=arguments.get("sku_filter"),
            location_filter=arguments.get("location_filter"),
        )

        skill = DemandForecast()
        result = await _run_sync(skill.run, input_data)
        return _format_forecast_result(result), True

    except Exception as e:
        logger.error("Demand forecast error: %s", e, exc_info=True)
        return f"Demand forecast error: {e}", False


def _format_forecast_result(result: Any) -> str:
    """Format forecast result as markdown."""
    lines = ["# Demand Forecast Report", ""]
    
    if hasattr(result, 'summary') and result.summary:
        s = result.summary
        lines.append(f"## Summary")
        lines.append(f"- **Total SKUs**: {s.get('total_skus', 0)}")
        lines.append(f"- **Total Predicted Volume**: {s.get('total_predicted_volume', 0):,}")
        lines.append(f"- **Avg MAPE**: {s.get('avg_mape', 0)}%")
        lines.append(f"- **Weighted MAPE**: {s.get('weighted_mape', 0)}%")
        lines.append(f"- **Method**: {getattr(result, 'method', 'N/A')}")
        lines.append(f"- **Horizon**: {getattr(result, 'horizon', 'N/A')} days")
        lines.append("")
        
        low_conf = s.get('low_confidence_skus', [])
        if low_conf:
            lines.append(f"⚠️ **Low Confidence SKUs** ({len(low_conf)}): {', '.join(low_conf[:10])}")
    
    if hasattr(result, 'forecasts') and result.forecasts:
        lines.append("## Top SKUs by Predicted Volume")
        lines.append("| SKU | Location | Method | Total | Daily | MAPE | Confidence |")
        lines.append("|-----|----------|--------|-------|-------|------|------------|")
        for f in result.forecasts[:20]:
            lines.append(
                f"| {f.sku_id} | {f.location_id or '-'} | {f.method_used} | "
                f"{f.total_predicted:,.0f} | {f.avg_daily_predicted:,.1f} | "
                f"{f.mape}% | {f.confidence_score:.0%} |"
            )
        if len(result.forecasts) > 20:
            lines.append(f"\n... and {len(result.forecasts) - 20} more SKUs")
    
    return "\n".join(lines)


# ── Demand Decompose ──────────────────────────────────────────────────────

DEMAND_DECOMPOSE_TOOL_SPEC = {
    "name": "demand_decompose",
    "description": (
        "Decompose time series into trend, seasonal, and residual components.\n\n"
        "Use this to UNDERSTAND demand patterns before forecasting:\n"
        "- Identifies underlying trend (growing/declining/stable)\n"
        "- Extracts seasonality patterns (weekly, monthly, yearly)\n"
        "- Isolates residuals/anomalies for investigation\n"
        "- Helps choose the right forecasting method\n\n"
        "Best used after data_profiler to understand data quality first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "demand_history": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Demand records with date and quantity fields",
            },
            "sku_id": {
                "type": "string",
                "description": "SKU to decompose (if omitted, aggregates all)",
            },
            "decomposition_method": {
                "type": "string",
                "enum": ["classical", "stl"],
                "default": "stl",
                "description": "Decomposition method: classical (additive) or stl (robust)",
            },
            "period": {
                "type": "integer",
                "description": "Seasonal period (e.g., 7 for weekly, 30 for monthly). Auto-detected if not specified.",
            },
        },
        "required": ["demand_history"],
    },
}


async def demand_decompose_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for demand decompose tool."""
    try:
        from supplymind.skills.demand.decompose.main import DemandDecompose
        from supplymind.skills.demand.decompose.schema import DecomposeInput

        input_data = DecomposeInput(
            demand_history=arguments["demand_history"],
            sku_id=arguments.get("sku_id"),
            decomposition_method=arguments.get("decomposition_method", "stl"),
            period=arguments.get("period"),
        )

        skill = DemandDecompose()
        result = await _run_sync(skill.run, input_data)

        output = f"# Demand Decomposition Analysis\n\n"
        if hasattr(result, 'trend'):
            output += f"## Trend: {'↑ Growing' if hasattr(result, 'trend_direction') else ''}\n"
        if hasattr(result, 'seasonality'):
            output += f"## Seasonality Strength: {result.seasonality}\n"
        if hasattr(result, 'model_dump'):
            output += "\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```"
        return output, True

    except Exception as e:
        return f"Demand decomposition error: {e}", False


# ── Demand Anomaly Detection ───────────────────────────────────────────────

DEMAND_ANOMALY_TOOL_SPEC = {
    "name": "demand_anomaly",
    "description": (
        "Detect anomalies and outliers in demand data.\n\n"
        "Use this to identify unusual patterns that need investigation:\n"
        "- Sudden spikes (promotions, stockouts at competitors)\n"
        "- Sudden drops (quality issues, data errors)\n"
        "- Level shifts (permanent changes in demand level)\n"
        "- Provides anomaly scores and suggested root causes\n\n"
        "Run BEFORE forecasting to avoid contaminating predictions with anomalous data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "demand_history": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Demand records with date and quantity fields",
            },
            "method": {
                "type": "string",
                "enum": ["zscore", "iqr", "isolation_forest"],
                "default": "iqr",
                "description": "Detection method",
            },
            "sensitivity": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "default": "medium",
                "description": "Detection sensitivity",
            },
        },
        "required": ["demand_history"],
    },
}


async def demand_anomaly_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for demand anomaly detection tool."""
    try:
        from supplymind.skills.demand.anomaly.main import DemandAnomaly
        from supplymind.skills.demand.anomaly.schema import AnomalyInput

        input_data = AnomalyInput(
            demand_history=arguments["demand_history"],
            method=arguments.get("method", "iqr"),
            sensitivity=arguments.get("sensitivity", "medium"),
        )

        skill = DemandAnomaly()
        result = await _run_sync(skill.run, input_data)

        output = "# Demand Anomaly Detection Report\n\n"
        if hasattr(result, 'anomalies') and result.anomalies:
            output += f"## Found {len(result.anomalies)} anomalies\n\n"
            for a in result.anomalies[:15]:
                a_dict = a.model_dump() if hasattr(a, 'model_dump') else dict(a)
                output += f"- **{a_dict.get('date', '?')}**: score={a_dict.get('score', '?')}, type={a_dict.get('type', '?')}\n"
        if hasattr(result, 'model_dump'):
            output += "\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```"
        return output, True

    except Exception as e:
        return f"Demand anomaly error: {e}", False


# ── New Product Forecast ─────────────────────────────────────────────────

DEMAND_NEWPRODUCT_TOOL_SPEC = {
    "name": "demand_newproduct",
    "description": (
        "Forecast demand for new products without historical sales data.\n\n"
        "Use this when launching new products:\n"
        "- Uses analog product matching (find similar existing products)\n"
        "- Applies diffusion curve models (Bass, logistic)\n"
        "- Incorporates product attributes (category, price point, seasonality)\n"
        "- Provides launch-phase demand ramp-up curve\n\n"
        "Requires product attributes and optionally reference product history."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "product_attributes": {
                "type": "object",
                "description": "New product attributes: category, price, launch_date, region, etc.",
            },
            "reference_products": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional: historical data from analogous/reference products",
            },
            "forecast_horizon": {
                "type": "integer",
                "default": 90,
                "description": "Days to forecast post-launch (default: 90)",
            },
            "curve_model": {
                "type": "string",
                "enum": ["bass", "logistic", "analog"],
                "default": "bass",
                "description": "Adoption curve model",
            },
        },
        "required": ["product_attributes"],
    },
}


async def demand_newproduct_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for new product demand forecast."""
    try:
        from supplymind.skills.demand.newproduct.main import DemandNewProduct
        from supplymind.skills.demand.newproduct.schema import NewProductInput

        input_data = NewProductInput(
            product_attributes=arguments["product_attributes"],
            reference_products=arguments.get("reference_products"),
            forecast_horizon=arguments.get("forecast_horizon", 90),
            curve_model=arguments.get("curve_model", "bass"),
        )

        skill = DemandNewProduct()
        result = await _run_sync(skill.run, input_data)

        output = "# New Product Demand Forecast\n\n"
        if hasattr(result, 'model_dump'):
            output += "```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```"
        return output, True

    except Exception as e:
        return f"New product forecast error: {e}", False


# ── Intermittent Demand ───────────────────────────────────────────────────

DEMAND_INTERMITTENT_TOOL_SPEC = {
    "name": "demand_intermittent",
    "description": (
        "Forecast intermittent/sporadic demand patterns (lumpy demand).\n\n"
        "Use this for SKUs with many zero-demand periods:\n"
        "- Spare parts, MRO items, slow-moving goods\n"
        "- Uses Croston method and its variants (SBA, TSB)\n"
        "- Optimizes for inventory cost, not forecast accuracy\n"
        "- Provides recommended review intervals\n\n"
        "Regular demand_forecast with method='croston' also works; "
        "this tool provides additional intermittent-specific analysis."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "demand_history": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Spare parts / slow-moving item demand records",
            },
            "sku_id": {
                "type": "string",
                "description": "Target SKU ID",
            },
            "service_level": {
                "type": "number",
                "default": 0.9,
                "description": "Target service level (0.8-0.99)",
            },
        },
        "required": ["demand_history"],
    },
}


async def demand_intermittent_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for intermittent demand forecast."""
    try:
        from supplymind.skills.demand.intermittent.main import DemandIntermittent
        from supplymind.skills.demand.intermittent.schema import IntermittentInput

        input_data = IntermittentInput(
            demand_history=arguments["demand_history"],
            sku_id=arguments.get("sku_id"),
            service_level=arguments.get("service_level", 0.9),
        )

        skill = DemandIntermittent()
        result = await _run_sync(skill.run, input_data)

        output = "# Intermittent Demand Analysis\n\n"
        if hasattr(result, 'model_dump'):
            output += "```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```"
        return output, True

    except Exception as e:
        return f"Intermittent demand error: {e}", False


# ── Demand Reconciliation ──────────────────────────────────────────────────

DEMAND_RECONCILE_TOOL_SPEC = {
    "name": "demand_reconcile",
    "description": (
        "Reconcile bottom-up and top-down forecast hierarchies.\n\n"
        "Use this when you have forecasts at different aggregation levels:\n"
        "- Aligns SKU-level forecasts with category/regional totals\n"
        "- Detects and resolves forecast conflicts across hierarchy levels\n"
        "- Uses proportionate or bottom-up reconciliation methods\n"
        "- Ensures forecasts roll up correctly to management targets\n\n"
        "Input requires both detailed (bottom-up) and aggregated (top-down) forecasts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "detailed_forecasts": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Bottom-up forecasts at SKU/location level",
            },
            "aggregated_targets": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Top-down targets at category/region level",
            },
            "reconciliation_method": {
                "type": "string",
                "enum": ["proportionate", "bottom_up", "top_down"],
                "default": "proportionate",
            },
        },
        "required": ["detailed_forecasts", "aggregated_targets"],
    },
}


async def demand_reconcile_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for demand reconciliation tool."""
    try:
        from supplymind.skills.demand.reconcile.main import DemandReconcile
        from supplymind.skills.demand.reconcile.schema import ReconcileInput

        input_data = ReconcileInput(
            detailed_forecasts=arguments["detailed_forecasts"],
            aggregated_targets=arguments["aggregated_targets"],
            reconciliation_method=arguments.get("reconciliation_method", "proportionate"),
        )

        skill = DemandReconcile()
        result = await _run_sync(skill.run, input_data)

        output = "# Demand Reconciliation Report\n\n"
        if hasattr(result, 'model_dump'):
            output += "```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```"
        return output, True

    except Exception as e:
        return f"Demand reconciliation error: {e}", False


# ── Utility ────────────────────────────────────────────────────────────────

async def _run_sync(func, *args, **kwargs):
    """Run sync function in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
