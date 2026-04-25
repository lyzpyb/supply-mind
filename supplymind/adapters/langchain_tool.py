"""LangChain Tool Wrapper — expose SupplyMind Skills as LangChain tools.

This adapter wraps any SupplyMind Skill as a LangChain BaseTool,
making it usable within LangChain/LangGraph agents.
"""

from __future__ import annotations

import json
from typing import Optional, Type

from supplymind.skills.common.what_if.schema import WhatIfInput


class SupplyMindTool:
    """LangChain-compatible tool wrapper for any SupplyMind Skill.

    Usage:
        tool = SupplyMindTool(
            skill_name="demand-forecast",
            description="Forecast demand based on historical sales",
        )
        result = tool.func(input_data={"horizon": 14, "method": "auto"})
    """

    def __init__(
        self,
        skill_name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        self.name = f"supplymind_{skill_name.replace('-', '_')}"
        self.description = description or f"SupplyMind {skill_name} skill"
        self.skill_name = skill_name
        self.input_schema = input_schema or {}

    def func(self, **kwargs) -> dict:
        """Execute the wrapped SupplyMind Skill."""
        try:
            mod_path, cls_name, input_cls_name = self._resolve_skill()
            import importlib
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            input_cls = getattr(
                importlib.import_module(mod_path.replace(".main", ".schema")),
                input_cls_name,
            )

            instance = cls()
            result = instance.run(input_cls(**kwargs))
            return result.model_dump() if hasattr(result, "model_dump") else dict(result)

        except Exception as e:
            return {"error": str(e), "skill": self.skill_name}

    def _resolve_skill(self) -> tuple[str, str, str]:
        """Map skill name to module/class names."""
        registry = {
            "data-profiler": ("supplymind.skills.common.data_profiler.main", "DataProfiler", "ProfilerInput"),
            "demand-forecast": ("supplymind.skills.demand.forecast.main", "DemandForecast", "ForecastInput"),
            "demand-decompose": ("supplymind.skills.demand.decompose.main", "DemandDecompose", "DecomposeInput"),
            "inventory-policy-sim": ("supplymind.skills.inventory.policy_sim.main", "InventoryPolicySim", "PolicySimInput"),
            "pricing-elasticity": ("supplymind.skills.pricing.elasticity.main", "PricingElasticity", "ElasticityInput"),
            "pricing-markdown": ("supplymind.skills.pricing.markdown.main", "PricingMarkdown", "MarkdownInput"),
            "fulfill-allocation": ("supplymind.skills.fulfillment.allocation.main", "FulfillmentAllocation", "AllocationInput"),
            "fulfill-routing": ("supplymind.skills.fulfillment.routing.main", "FulfillmentRouting", "RoutingInput"),
            "what-if": ("supplymind.skills.common.what_if.main", "WhatIfSimulator", "WhatIfInput"),
        }
        if self.skill_name in registry:
            return registry[self.skill_name]
        # Fallback convention
        parts = self.skill_name.replace("-", "_")
        return (
            f"supplymind.skills.{parts}.main",
            "".join(p.title() for p in parts.split("_")),
            f"{parts.title().replace('_', '')}Input",
        )


def get_all_tools() -> list[SupplyMindTool]:
    """Get all SupplyMind skills as LangChain-compatible tools."""
    tool_defs = [
        {"skill_name": "data-profiler", "description": "Profile and analyze supply chain data quality"},
        {"skill_name": "demand-forecast", "description": "Generate demand forecasts with confidence intervals"},
        {"skill_name": "demand-decompose", "description": "Decompose time series into trend/seasonal/residual"},
        {"skill_name": "inventory-policy-sim", "description": "Simulate inventory policies with Monte Carlo"},
        {"skill_name": "pricing-elasticity", "description": "Estimate price elasticity from historical data"},
        {"skill_name": "pricing-markdown", "description": "Optimize markdown/clearance pricing strategy"},
        {"skill_name": "fulfill-allocation", "description": "Allocate inventory across multiple warehouses"},
        {"skill_name": "fulfill-routing", "description": "Optimize delivery routes using TSP"},
        {"skill_name": "what-if", "description": "Run multi-scenario what-if simulations"},
    ]
    return [SupplyMindTool(**td) for td in tool_defs]
