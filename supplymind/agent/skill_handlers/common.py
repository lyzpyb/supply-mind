"""
Common Skill Handlers — async bridges for data_profiler, report_generator, what_if.

Each handler follows the ml-intern pattern:
  1. Receive arguments dict from ToolRouter
  2. Validate and convert to the skill's Pydantic Input schema
  3. Call skill.run() (sync) via asyncio.to_thread
  4. Format output as readable markdown string
  5. Return (output_string, success_bool)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Data Profiler ──────────────────────────────────────────────────────────

DATA_PROFILER_TOOL_SPEC = {
    "name": "data_profiler",
    "description": (
        "Profile and analyze supply chain data quality. "
        "Detects missing values, outliers, duplicates, and provides statistical summaries.\n\n"
        "Use this as the FIRST step when working with any new supply chain dataset:\n"
        "- Validates data format and completeness\n"
        "- Identifies data quality issues that would affect other skills\n"
        "- Provides per-column statistics (mean, std, min, max, missing %)\n"
        "- Suggests data cleaning actions\n\n"
        "Input can be raw demand records, inventory snapshots, or pricing history."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Array of data records (dicts). Each record should contain "
                    "supply chain fields like sku_id, quantity, date, location_id, etc. "
                    "Accepts sparse input — missing fields get defaults."
                ),
            },
            "profile_type": {
                "type": "string",
                "enum": ["full", "quick", "schema_only"],
                "default": "full",
                "description": "Profile depth: full (all stats), quick (summary only), schema_only (column names + types)",
            },
        },
        "required": ["data"],
    },
}


async def data_profiler_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for data profiler tool."""
    try:
        from supplymind.skills.common.data_profiler.main import DataProfiler
        from supplymind.skills.common.data_profiler.schema import ProfilerInput

        data = arguments.get("data", [])
        profile_type = arguments.get("profile_type", "full")

        if not data:
            return "No data provided. Please supply an array of data records to profile.", False

        # Build input — handle both list-of-dicts and wrapped format
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            if "demand_history" not in data[0] and "quantity" in data[0]:
                # Raw demand records format
                input_data = ProfilerInput(demand_history=data)
            else:
                # Wrapped format or mixed
                input_data = ProfilerInput(demand_history=data)
        else:
            input_data = ProfilerInput(demand_history=data)

        skill = DataProfiler()
        result = await _run_sync(skill.run, input_data)

        # Format as markdown
        output = _format_profiler_result(result)
        return output, True

    except Exception as e:
        logger.error("Data profiler error: %s", e, exc_info=True)
        return f"Data profiler error: {e}", False


def _format_profiler_result(result: Any) -> str:
    """Format DataProfiler result as readable markdown."""
    lines = ["# Supply Chain Data Profile Report", ""]
    
    if hasattr(result, 'overview') and result.overview:
        lines.append("## Overview")
        for k, v in result.overview.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    
    if hasattr(result, 'columns') and result.columns:
        lines.append("## Column Analysis")
        lines.append("| Column | Type | Missing | Unique | Min | Max | Mean |")
        lines.append("|--------|------|---------|--------|-----|-----|------|")
        for col in result.columns:
            col_dict = col.model_dump() if hasattr(col, 'model_dump') else dict(col)
            lines.append(
                f"| {col_dict.get('name', 'N/A')} | {col_dict.get('type', 'N/A')} | "
                f"{col_dict.get('missing_pct', 0)}% | {col_dict.get('unique_count', 'N/A')} | "
                f"{col_dict.get('min', 'N/A')} | {col_dict.get('max', 'N/A')} | "
                f"{col_dict.get('mean', 'N/A')} |"
            )
        lines.append("")
    
    if hasattr(result, 'quality_score'):
        lines.append(f"## Quality Score: {result.quality_score}/100")
    
    if hasattr(result, 'recommendations') and result.recommendations:
        lines.append("## Recommendations")
        for r in result.recommendations:
            lines.append(f"- {r}")
    
    if hasattr(result, 'model_dump'):
        # Fallback: include full JSON
        lines.append("\n## Full Result (JSON)")
        lines.append("```json")
        lines.append(json.dumps(result.model_dump(), indent=2, default=str)[:3000])
        lines.append("```")
    
    return "\n".join(lines)


# ── Report Generator ───────────────────────────────────────────────────────

REPORT_GENERATOR_TOOL_SPEC = {
    "name": "report_generator",
    "description": (
        "Generate a formatted analysis report from supply chain data and results.\n\n"
        "Use this to produce human-readable reports combining outputs from multiple skills:\n"
        "- Combines forecast results, inventory analysis, and pricing recommendations\n"
        "- Outputs structured markdown with tables, charts (ASCII), and insights\n"
        "- Suitable for sharing with stakeholders or including in dashboards\n\n"
        "Typically used AFTER running other skills (forecast, inventory analysis, etc.)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Report title (e.g., 'Q3 Demand Planning Report')",
            },
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "content": {"type": "string"},
                        "data": {"type": "object"},
                        "section_type": {
                            "type": "string",
                            "enum": ["text", "table", "summary", "chart"],
                        },
                    },
                },
                "description": "Report sections with headings and content/data",
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "html", "json"],
                "default": "markdown",
            },
        },
        "required": ["title", "sections"],
    },
}


async def report_generator_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for report generator tool."""
    try:
        from supplymind.skills.common.report_generator.main import ReportGenerator
        from supplymind.skills.common.report_generator.schema import ReportInput

        input_data = ReportInput(
            title=arguments.get("title", "Supply Chain Report"),
            sections=arguments.get("sections", []),
            format=arguments.get("format", "markdown"),
        )

        skill = ReportGenerator()
        result = await _run_sync(skill.run, input_data)

        output = result.content if hasattr(result, 'content') else str(result)
        return output, True

    except Exception as e:
        logger.error("Report generator error: %s", e, exc_info=True)
        return f"Report generator error: {e}", False


# ── What-If Simulator ─────────────────────────────────────────────────────

WHAT_IF_TOOL_SPEC = {
    "name": "what_if",
    "description": (
        "Run multi-scenario what-if simulations on supply chain decisions.\n\n"
        "Use this to compare outcomes of different decisions BEFORE committing:\n"
        "- Compare inventory policies (e.g., safety stock at 90% vs 95% service level)\n"
        "- Evaluate promotion impact on demand and inventory\n"
        "- Test supplier lead time changes\n"
        "- Analyze price change effects on revenue and margin\n\n"
        "Returns a comparison table across scenarios with recommended action.\n"
        "Requires base scenario data + list of scenarios to test."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "base_scenario": {
                "type": "object",
                "description": (
                    "Base/current scenario parameters. Include relevant fields "
                    "like demand_history, inventory_levels, pricing, lead_times, etc."
                ),
            },
            "scenarios": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "List of scenarios to test. Each scenario is a dict of "
                    "parameter overrides (e.g., {'service_level': 0.95}, "
                    "{'price_change': -0.1}). Requires 'name' field for identification."
                ),
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Metrics to evaluate for each scenario. Examples: "
                    "revenue, fill_rate, stockout_cost, holding_cost, margin, profit"
                ),
            },
            "horizon_days": {
                "type": "integer",
                "default": 30,
                "description": "Simulation horizon in days (default: 30)",
            },
        },
        "required": ["base_scenario", "scenarios"],
    },
}


async def what_if_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for what-if simulation tool."""
    try:
        from supplymind.skills.common.what_if.main import WhatIfSimulator
        from supplymind.skills.common.what_if.schema import WhatIfInput

        input_data = WhatIfInput(
            base_scenario=arguments["base_scenario"],
            scenarios=arguments["scenarios"],
            metrics=arguments.get("metrics", ["revenue", "fill_rate", "stockout_cost"]),
            horizon_days=arguments.get("horizon_days", 30),
        )

        skill = WhatIfSimulator()
        result = await _run_sync(skill.run, input_data)

        # Format as comparison table
        output = _format_whatif_result(result)
        return output, True

    except Exception as e:
        logger.error("What-if error: %s", e, exc_info=True)
        return f"What-if simulation error: {e}", False


def _format_whatif_result(result: Any) -> str:
    """Format What-If result as readable markdown."""
    lines = ["# What-If Scenario Comparison", ""]
    
    if hasattr(result, 'scenario_results') and result.scenario_results:
        lines.append("## Results by Scenario")
        lines.append("| Scenario | " + " | ".join(
            getattr(s, 'name', s.keys()[0] if isinstance(s, dict) else '?')
            for s in (result.scenario_results[:1] if result.scenario_results else [])
        ) + " |")  # header handled below
        lines.append("|----------|")
        
        for sr in result.scenario_results:
            sr_dict = sr.model_dump() if hasattr(sr, 'model_dump') else dict(sr)
            name = sr_dict.get('name', 'Scenario')
            metrics_str = " | ".join(
                f"{k}: {v}" for k, v in sr_dict.items() if k != 'name'
            )
            lines.append(f"| {name} | {metrics_str} |")
        lines.append("")
    
    if hasattr(result, 'recommended_scenario'):
        lines.append(f"## Recommended: **{result.recommended_scenario}**")
        lines.append("")
    
    if hasattr(result, 'insights') and result.insights:
        lines.append("## Key Insights")
        for insight in result.insights:
            lines.append(f"- {insight}")
    
    if hasattr(result, 'model_dump'):
        lines.append("\n## Full Result (JSON)")
        lines.append("```json")
        lines.append(json.dumps(result.model_dump(), indent=2, default=str)[:4000])
        lines.append("```")
    
    return "\n".join(lines)


# ── Utility ────────────────────────────────────────────────────────────────

async def _run_sync(func, *args, **kwargs):
    """Run a synchronous function in a thread pool to avoid blocking event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
