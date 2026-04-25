"""
SupplyMind Agent Tool System — ToolSpec, ToolRouter, and built-in tool registry.

Ported from HuggingFace ml-intern's agent/core/tools.py pattern.
Provides a unified interface for exposing SupplyMind skills as agent-callable tools.

Architecture:
    Skill (Python class) → TOOL_SPEC (dict) → handler (async bridge) → ToolSpec (dataclass) → ToolRouter

Each skill module exports:
    - TOOL_SPEC: dict with name, description, parameters (JSON Schema)
    - handler(): async function bridging arguments to the skill's run() method
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import traceback
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Tool specification for LLM function calling.

    Attributes:
        name: Tool identifier used in LLM function calls (e.g., "demand_forecast")
        description: Natural language description telling the LLM when and how to use this tool
        parameters: JSON Schema dict describing the tool's input parameters
        handler: Async callable that executes the tool. Signature: (args: dict) -> (str, bool)
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Optional[Callable[[dict[str, Any]], Awaitable[tuple[str, bool]]]] = None


class ToolRouter:
    """Routes tool calls to appropriate handlers.

    Manages a registry of ToolSpec instances and provides:
    - Registration of tools
    - Lookup by name
    - Execution via call_tool()
    - Export to OpenAI function-calling format

    Usage:
        router = ToolRouter()
        router.register_tool(my_tool_spec)
        specs = router.get_tool_specs_for_llm()  # OpenAI format
        output, success = await router.call_tool("tool_name", {"arg": "value"})
    """

    def __init__(self):
        self.tools: dict[str, ToolSpec] = {}

    def register_tool(self, tool: ToolSpec) -> None:
        """Register a tool spec."""
        self.tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def register_tools(self, tools: Sequence[ToolSpec]) -> None:
        """Register multiple tool specs at once."""
        for tool in tools:
            self.register_tool(tool)

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Get a tool spec by name."""
        return self.tools.get(name)

    def get_tool_specs_for_llm(self) -> list[dict[str, Any]]:
        """Export all registered tools in OpenAI function-calling format.

        Returns:
            List of dicts with type="function" and function={name, description, parameters}
        """
        specs = []
        for tool in self.tools.values():
            specs.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return specs

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        format: str = "markdown",
    ) -> tuple[str, bool] | tuple[dict[str, Any], bool]:
        """Execute a tool by name with given arguments.

        Args:
            tool_name: The name of the tool to execute
            arguments: Dict of argument name -> value
            format: Output format — "markdown" (default), "json", or "both"

        Returns:
            Tuple of (output, success_bool).
            When format="markdown": output is str.
            When format="json": output is dict with {markdown, structured}.
            When format="both": output is dict with {markdown, structured}.
        """
        tool = self.tools.get(tool_name)
        if tool is None:
            msg = f"Unknown tool: '{tool_name}'. Available tools: {', '.join(sorted(self.tools.keys()))}"
            if format == "markdown":
                return msg, False
            return {"markdown": msg, "structured": None}, False

        if tool.handler is None:
            msg = f"Tool '{tool_name}' has no handler configured"
            if format == "markdown":
                return msg, False
            return {"markdown": msg, "structured": None}, False

        try:
            import time as _time
            _t0 = _time.time()
            markdown_output, success = await tool.handler(arguments)
            _elapsed = (_time.time() - _t0) * 1000

            try:
                from supplymind.enterprise import get_audit_logger
                get_audit_logger().log_skill_execution(
                    skill=tool_name, arguments=arguments,
                    outcome="success" if success else "error",
                    duration_ms=_elapsed,
                )
            except Exception:
                pass

            if format == "markdown":
                return markdown_output, success

            structured = _extract_json_from_markdown(markdown_output)
            result = {"markdown": markdown_output, "structured": structured}
            return result, success

        except Exception as e:
            logger.error("Error executing tool '%s': %s", tool_name, e, exc_info=True)

            try:
                from supplymind.enterprise import get_audit_logger
                get_audit_logger().log_skill_execution(
                    skill=tool_name, arguments=arguments,
                    outcome="error", error=str(e),
                )
            except Exception:
                pass

            msg = f"Error executing {tool_name}: {e}\n{traceback.format_exc()}"
            if format == "markdown":
                return msg, False
            return {"markdown": msg, "structured": None}, False

    async def call_tool_parallel(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[tuple[str, bool]]:
        """Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of dicts with "name" and "arguments" keys

        Returns:
            List of (output_string, bool_success) tuples in same order
        """
        async def _exec_one(tc: dict) -> tuple[str, bool]:
            return await self.call_tool(tc["name"], tc.get("arguments", {}))

        results = await asyncio.gather(*[_exec_one(tc) for tc in tool_calls])
        return list(results)

    @property
    def tool_names(self) -> list[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self.tools.keys())

    def __len__(self) -> int:
        return len(self.tools)

    def __contains__(self, name: str) -> bool:
        return name in self.tools


def _extract_json_from_markdown(markdown: str) -> dict | None:
    """Extract structured JSON from handler markdown output.

    Handlers embed JSON in two ways:
    1. ```json ... ``` code blocks (most handlers do this via model_dump())
    2. <!-- JSON: {...} --> HTML comments (explicit structured data)

    Returns the last/largest JSON object found, or None.
    """
    # Try HTML comment first (explicit structured data takes priority)
    comment_match = re.search(r'<!--\s*JSON:\s*(\{.*?\})\s*-->', markdown, re.DOTALL)
    if comment_match:
        try:
            return json.loads(comment_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try ```json code blocks
    json_blocks = re.findall(r'```json\s*\n(.*?)\n```', markdown, re.DOTALL)
    if json_blocks:
        for block in reversed(json_blocks):
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

    return None


# ============================================================================
# SKILL REGISTRY — maps skill names to their Python module paths
# ============================================================================

_SKILL_REGISTRY: dict[str, dict] = {
    # ── Common ──
    "data_profiler": {
        "module": "supplymind.agent.skill_handlers.common",
        "spec_attr": "DATA_PROFILER_TOOL_SPEC",
        "handler_attr": "data_profiler_handler",
        "description": "Profile and analyze supply chain data quality",
    },
    "report_generator": {
        "module": "supplymind.agent.skill_handlers.common",
        "spec_attr": "REPORT_GENERATOR_TOOL_SPEC",
        "handler_attr": "report_generator_handler",
        "description": "Generate formatted analysis reports from supply chain data",
    },
    "what_if": {
        "module": "supplymind.agent.skill_handlers.common",
        "spec_attr": "WHAT_IF_TOOL_SPEC",
        "handler_attr": "what_if_handler",
        "description": "Run multi-scenario what-if simulations on supply chain decisions",
    },

    # ── Demand ──
    "demand_forecast": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_FORECAST_TOOL_SPEC",
        "handler_attr": "demand_forecast_handler",
        "description": "Generate demand forecasts with confidence intervals",
    },
    "demand_decompose": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_DECOMPOSE_TOOL_SPEC",
        "handler_attr": "demand_decompose_handler",
        "description": "Decompose time series into trend/seasonal/residual components",
    },
    "demand_anomaly": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_ANOMALY_TOOL_SPEC",
        "handler_attr": "demand_anomaly_handler",
        "description": "Detect anomalies and outliers in demand data",
    },
    "demand_newproduct": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_NEWPRODUCT_TOOL_SPEC",
        "handler_attr": "demand_newproduct_handler",
        "description": "Forecast demand for new products using analog/curve methods",
    },
    "demand_intermittent": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_INTERMITTENT_TOOL_SPEC",
        "handler_attr": "demand_intermittent_handler",
        "description": "Forecast intermittent/sporadic demand patterns",
    },
    "demand_reconcile": {
        "module": "supplymind.agent.skill_handlers.demand",
        "spec_attr": "DEMAND_RECONCILE_TOOL_SPEC",
        "handler_attr": "demand_reconcile_handler",
        "description": "Reconcile bottom-up and top-down forecast hierarchies",
    },

    # ── Inventory ──
    "inventory_reorder": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_REORDER_TOOL_SPEC",
        "handler_attr": "inventory_reorder_handler",
        "description": "Calculate optimal reorder points and order quantities",
    },
    "inventory_safety_stock": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_SAFETY_STOCK_TOOL_SPEC",
        "handler_attr": "inventory_safety_stock_handler",
        "description": "Calculate safety stock levels for target service levels",
    },
    "inventory_policy_sim": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_POLICY_SIM_TOOL_SPEC",
        "handler_attr": "inventory_policy_sim_handler",
        "description": "Simulate inventory policies with Monte Carlo methods",
    },
    "inventory_classify": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_CLASSIFY_TOOL_SPEC",
        "handler_attr": "inventory_classify_handler",
        "description": "Classify SKUs by ABC/XYZ analysis for segmentation",
    },
    "inventory_multi_echelon": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_MULTI_ECHELON_TOOL_SPEC",
        "handler_attr": "inventory_multi_echelon_handler",
        "description": "Optimize inventory across multi-echelon supply networks",
    },
    "inventory_newsvendor": {
        "module": "supplymind.agent.skill_handlers.inventory",
        "spec_attr": "INVENTORY_NEWSVENDOR_TOOL_SPEC",
        "handler_attr": "inventory_newsvendor_handler",
        "description": "Solve newsvendor problems for perishable/seasonal products",
    },

    # ── Pricing ──
    "pricing_elasticity": {
        "module": "supplymind.agent.skill_handlers.pricing",
        "spec_attr": "PRICING_ELASTICITY_TOOL_SPEC",
        "handler_attr": "pricing_elasticity_handler",
        "description": "Estimate price elasticity from historical sales data",
    },
    "pricing_markdown": {
        "module": "supplymind.agent.skill_handlers.pricing",
        "spec_attr": "PRICING_MARKDOWN_TOOL_SPEC",
        "handler_attr": "pricing_markdown_handler",
        "description": "Optimize markdown/clearance pricing strategy",
    },
    "pricing_lifecycle": {
        "module": "supplymind.agent.skill_handlers.pricing",
        "spec_attr": "PRICING_LIFECYCLE_TOOL_SPEC",
        "handler_attr": "pricing_lifecycle_handler",
        "description": "Detect product lifecycle stage and recommend pricing",
    },
    "pricing_bundling": {
        "module": "supplymind.agent.skill_handlers.pricing",
        "spec_attr": "PRICING_BUNDLING_TOOL_SPEC",
        "handler_attr": "pricing_bundling_handler",
        "description": "Recommend product bundles and bundle pricing",
    },

    # ── Fulfillment ──
    "fulfill_allocation": {
        "module": "supplymind.agent.skill_handlers.fulfillment",
        "spec_attr": "FULFILL_ALLOCATION_TOOL_SPEC",
        "handler_attr": "fulfill_allocation_handler",
        "description": "Allocate inventory across multiple warehouses/customers",
    },
    "fulfill_routing": {
        "module": "supplymind.agent.skill_handlers.fulfillment",
        "spec_attr": "FULFILL_ROUTING_TOOL_SPEC",
        "handler_attr": "fulfill_routing_handler",
        "description": "Optimize delivery routes using TSP algorithms",
    },
    "fulfill_wave": {
        "module": "supplymind.agent.skill_handlers.fulfillment",
        "spec_attr": "FULFILL_WAVE_TOOL_SPEC",
        "handler_attr": "fulfill_wave_handler",
        "description": "Plan wave picking batches for warehouse operations",
    },
    "fulfill_capacity": {
        "module": "supplymind.agent.skill_handlers.fulfillment",
        "spec_attr": "FULFILL_CAPACITY_TOOL_SPEC",
        "handler_attr": "fulfill_capacity_handler",
        "description": "Check fulfillment capacity and identify bottlenecks",
    },
}


def create_supplymind_tools(
    skill_names: Optional[list[str]] = None,
) -> list[ToolSpec]:
    """Create ToolSpec instances for SupplyMind skills.

    This is the main entry point for creating agent-ready tools from
    SupplyMind's skill library. Each tool follows the ml-intern pattern:

        TOOL_SPEC = {name, description, parameters}  # ← LLM sees this
        async def handler(args): ...                 # ← execution logic

    Args:
        skill_names: Optional list of skill names to create.
                     If None, all registered skills are created.

    Returns:
        List of ToolSpec instances ready for registration with ToolRouter.
    """
    names = skill_names or list(_SKILL_REGISTRY.keys())
    tools = []

    for name in names:
        entry = _SKILL_REGISTRY.get(name)
        if entry is None:
            logger.warning("Unknown skill: %s — skipping", name)
            continue

        try:
            mod = __import__(entry["module"], fromlist=[entry["spec_attr"], entry["handler_attr"]])
            spec = getattr(mod, entry["spec_attr"])
            handler = getattr(mod, entry["handler_attr"])

            tools.append(ToolSpec(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                handler=handler,
            ))
            logger.debug("Created tool: %s (%s)", spec["name"], name)

        except ImportError as e:
            logger.warning("Could not import module for skill '%s': %s", name, e)
        except AttributeError as e:
            logger.warning("Missing spec/handler for skill '%s': %s", name, e)

    logger.info("Created %d SupplyMind agent tools: %s", len(tools), [t.name for t in tools])
    return tools


def get_tool_router(
    skill_names: Optional[list[str]] = None,
) -> ToolRouter:
    """Create a pre-populated ToolRouter with all SupplyMind tools.

    Convenience function that creates tools and registers them in one call.

    Args:
        skill_names: Optional list of skill names. If None, all skills.

    Returns:
        ToolRouter instance with all requested tools registered.
    """
    router = ToolRouter()
    tools = create_supplymind_tools(skill_names)
    router.register_tools(tools)
    return router


def get_skill_registry() -> dict[str, dict]:
    """Return the full skill registry metadata (for introspection)."""
    return dict(_SKILL_REGISTRY)
