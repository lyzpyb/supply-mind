"""
MCP Server — exposes all 23 SupplyMind skills via Model Context Protocol.

Uses the official `mcp` SDK (FastMCP pattern) for full protocol compliance.
Supports stdio and SSE transports, compatible with Claude Desktop, Cursor, etc.

Install: pip install supplymind[mcp]
Run:     supplymind mcp-serve --transport stdio

All 23 tools across 5 domains:
  Common:     data_profiler, report_generator, what_if
  Demand:     demand_forecast, demand_decompose, demand_anomaly,
              demand_newproduct, demand_intermittent, demand_reconcile
  Inventory:  inventory_reorder, inventory_safety_stock, inventory_policy_sim,
              inventory_classify, inventory_multi_echelon, inventory_newsvendor
  Pricing:    pricing_elasticity, pricing_markdown, pricing_lifecycle, pricing_bundling
  Fulfillment: fulfill_allocation, fulfill_routing, fulfill_wave, fulfill_capacity
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)

_MCP_AVAILABLE = False
try:
    from mcp.server.fastmcp import FastMCP
    _MCP_AVAILABLE = True
except ImportError:
    pass


def _create_mcp_server() -> "FastMCP":
    """Create and configure the MCP server with all SupplyMind tools."""
    if not _MCP_AVAILABLE:
        raise ImportError(
            "MCP SDK not installed. Install with: pip install supplymind[mcp]\n"
            "Or directly: pip install mcp>=1.0.0"
        )

    mcp = FastMCP(
        "SupplyMind",
        version="0.1.0",
        description="Supply chain planning agent toolkit with 23 skills",
    )

    # PLACEHOLDER_TOOLS
    return mcp


def _register_all_tools(mcp: "FastMCP"):
    """Register all 23 SupplyMind tools on the FastMCP server."""

    # ── Common Tools ──

    @mcp.tool()
    async def data_profiler(data: list[dict], profile_type: str = "quick") -> str:
        """Profile and analyze supply chain data quality.
        Detects missing values, outliers, duplicates, and provides statistical summaries.
        Use as the FIRST step when working with any new dataset."""
        return await _call_skill_handler("data_profiler", {
            "data": data, "profile_type": profile_type,
        })

    @mcp.tool()
    async def report_generator(title: str, sections: list[dict], format: str = "markdown") -> str:
        """Generate formatted analysis reports from supply chain data.
        Supports markdown and HTML output formats."""
        return await _call_skill_handler("report_generator", {
            "title": title, "sections": sections, "format": format,
        })

    @mcp.tool()
    async def what_if(base_params: dict, scenarios: list[dict], skill_name: str = "inventory-policy-sim") -> str:
        """Run multi-scenario what-if simulation comparing different parameter sets.
        Useful for comparing conservative vs aggressive strategies."""
        return await _call_skill_handler("what_if", {
            "base_params": base_params, "scenarios": scenarios, "skill_name": skill_name,
        })

    # ── Demand Tools ──

    @mcp.tool()
    async def demand_forecast(
        demand_history: list[dict],
        horizon: int = 14,
        method: str = "auto",
        confidence_level: float = 0.95,
    ) -> str:
        """Generate demand forecasts with confidence intervals.
        Methods: auto, ma, ema, holt_winters, croston.
        Input: demand records with sku_id, date, quantity fields."""
        return await _call_skill_handler("demand_forecast", {
            "demand_history": demand_history, "horizon": horizon,
            "method": method, "confidence_level": confidence_level,
        })

    @mcp.tool()
    async def demand_decompose(demand_history: list[dict], period: int | None = None) -> str:
        """Decompose time series into trend, seasonal, and residual components using STL."""
        args: dict[str, Any] = {"demand_history": demand_history}
        if period is not None:
            args["period"] = period
        return await _call_skill_handler("demand_decompose", args)

    @mcp.tool()
    async def demand_anomaly(demand_history: list[dict], method: str = "zscore", threshold: float = 3.0) -> str:
        """Detect anomalies and outliers in demand data.
        Methods: zscore, iqr. Returns flagged records and cleaned data."""
        return await _call_skill_handler("demand_anomaly", {
            "demand_history": demand_history, "method": method, "threshold": threshold,
        })

    @mcp.tool()
    async def demand_newproduct(
        sku_id: str, category: str, analog_skus: list[str] | None = None,
        weeks_since_launch: int = 0,
    ) -> str:
        """Forecast demand for new products using analog/curve methods.
        Handles cold-start by matching similar existing products."""
        return await _call_skill_handler("demand_newproduct", {
            "sku_id": sku_id, "category": category,
            "analog_skus": analog_skus or [], "weeks_since_launch": weeks_since_launch,
        })

    @mcp.tool()
    async def demand_intermittent(demand_history: list[dict], variant: str = "sba") -> str:
        """Forecast intermittent/sporadic demand using Croston variants.
        Variants: classic, sba (Syntetos-Boylan), tsb."""
        return await _call_skill_handler("demand_intermittent", {
            "demand_history": demand_history, "variant": variant,
        })

    @mcp.tool()
    async def demand_reconcile(forecasts: list[dict], method: str = "bottom_up") -> str:
        """Reconcile bottom-up and top-down forecast hierarchies.
        Methods: bottom_up, top_down, middle_out."""
        return await _call_skill_handler("demand_reconcile", {
            "forecasts": forecasts, "method": method,
        })

    # ── Inventory Tools ──

    @mcp.tool()
    async def inventory_reorder(
        sku_id: str, current_inventory: float, demand_forecast: list[float],
        lead_time_days: float = 7.0, service_level: float = 0.95,
    ) -> str:
        """Calculate optimal reorder points and order quantities.
        Returns EOQ, ROP, and urgency-ranked suggestions."""
        return await _call_skill_handler("inventory_reorder", {
            "sku_id": sku_id, "current_inventory": current_inventory,
            "demand_forecast": demand_forecast, "lead_time_days": lead_time_days,
            "target_service_level": service_level,
        })

    @mcp.tool()
    async def inventory_safety_stock(
        items: list[dict], target_service_level: float = 0.95, method: str = "service_level",
    ) -> str:
        """Calculate safety stock levels for target service levels.
        Methods: service_level, stochastic (Monte Carlo)."""
        return await _call_skill_handler("inventory_safety_stock", {
            "items": items, "target_service_level": target_service_level, "method": method,
        })

    @mcp.tool()
    async def inventory_policy_sim(
        sku_id: str = "SKU001", demand_mean: float = 100.0, demand_std: float = 30.0,
        lead_time_mean: float = 7.0, lead_time_std: float = 2.0,
        reorder_point: float = 200.0, order_quantity: float = 500.0,
        simulation_days: int = 365, n_simulations: int = 100,
    ) -> str:
        """Simulate inventory policies with Monte Carlo methods.
        Compare (s,Q) and (s,S) policies under demand/lead-time uncertainty."""
        return await _call_skill_handler("inventory_policy_sim", {
            "sku_id": sku_id, "demand_mean": demand_mean, "demand_std": demand_std,
            "lead_time_mean": lead_time_mean, "lead_time_std": lead_time_std,
            "reorder_point": reorder_point, "order_quantity": order_quantity,
            "simulation_days": simulation_days, "n_simulations": n_simulations,
        })

    @mcp.tool()
    async def inventory_classify(items: list[dict]) -> str:
        """Classify SKUs by ABC-XYZ analysis for inventory segmentation.
        ABC = revenue contribution, XYZ = demand variability."""
        return await _call_skill_handler("inventory_classify", {"items": items})

    @mcp.tool()
    async def inventory_multi_echelon(config: dict) -> str:
        """Optimize inventory across multi-echelon supply networks.
        Supports 2-level networks (factory→DC or DC→store)."""
        return await _call_skill_handler("inventory_multi_echelon", config)

    @mcp.tool()
    async def inventory_newsvendor(
        unit_price: float, unit_cost: float, salvage_value: float = 0.0,
        demand_mean: float = 100.0, demand_std: float = 30.0,
    ) -> str:
        """Solve newsvendor problems for perishable/seasonal products.
        Finds optimal order quantity balancing overage vs underage costs."""
        return await _call_skill_handler("inventory_newsvendor", {
            "unit_price": unit_price, "unit_cost": unit_cost,
            "salvage_value": salvage_value,
            "demand_mean": demand_mean, "demand_std": demand_std,
        })

    # ── Pricing Tools ──

    @mcp.tool()
    async def pricing_elasticity(prices: list[float], quantities: list[float]) -> str:
        """Estimate price elasticity from historical price-quantity data.
        Returns elasticity coefficient, classification, and revenue-optimal price."""
        return await _call_skill_handler("pricing_elasticity", {
            "prices": prices, "quantities": quantities,
        })

    @mcp.tool()
    async def pricing_markdown(
        current_stock: float, unit_cost: float, original_price: float,
        elasticity: float = -2.0, days_remaining: int = 30,
    ) -> str:
        """Optimize phased markdown/clearance pricing strategy.
        Maximizes revenue under time pressure for excess inventory."""
        return await _call_skill_handler("pricing_markdown", {
            "current_stock": current_stock, "unit_cost": unit_cost,
            "original_price": original_price, "elasticity": elasticity,
            "days_remaining": days_remaining,
        })

    @mcp.tool()
    async def pricing_lifecycle(weekly_sales: list[float], weeks_since_launch: int | None = None) -> str:
        """Detect product lifecycle stage (intro/growth/maturity/decline).
        Recommends pricing strategy for each stage."""
        args: dict[str, Any] = {"weekly_sales": weekly_sales}
        if weeks_since_launch is not None:
            args["weeks_since_launch"] = weeks_since_launch
        return await _call_skill_handler("pricing_lifecycle", args)

    @mcp.tool()
    async def pricing_bundling(transactions: list[dict], min_support: float = 0.05) -> str:
        """Recommend product bundles and bundle pricing.
        Analyzes co-purchase patterns to find complementary products."""
        return await _call_skill_handler("pricing_bundling", {
            "transactions": transactions, "min_support": min_support,
        })

    # ── Fulfillment Tools ──

    @mcp.tool()
    async def fulfill_allocation(orders: list[dict], inventory: list[dict]) -> str:
        """Allocate inventory across multiple warehouses/customers.
        Uses priority rules + LP optimization with service level constraints."""
        return await _call_skill_handler("fulfill_allocation", {
            "orders": orders, "inventory": inventory,
        })

    @mcp.tool()
    async def fulfill_routing(locations: list[dict], vehicle_capacity: float = 1000.0) -> str:
        """Optimize delivery routes using nearest-neighbor + 2-opt TSP.
        Input: locations with lat, lon, demand fields."""
        return await _call_skill_handler("fulfill_routing", {
            "locations": locations, "vehicle_capacity": vehicle_capacity,
        })

    @mcp.tool()
    async def fulfill_wave(orders: list[dict], wave_capacity: int = 50) -> str:
        """Plan wave picking batches for warehouse operations.
        Groups orders by zone/priority for efficient picking."""
        return await _call_skill_handler("fulfill_wave", {
            "orders": orders, "wave_capacity": wave_capacity,
        })

    @mcp.tool()
    async def fulfill_capacity(resources: list[dict]) -> str:
        """Check fulfillment capacity and identify bottlenecks.
        Evaluates warehouse/production capacity against demand."""
        return await _call_skill_handler("fulfill_capacity", {"resources": resources})


async def _call_skill_handler(skill_name: str, arguments: dict) -> str:
    """Bridge: MCP tool call → SupplyMind agent handler → markdown + structured output."""
    from supplymind.agent.tools import create_supplymind_tools, _extract_json_from_markdown

    tools = create_supplymind_tools([skill_name])
    if not tools:
        return f"Error: skill '{skill_name}' not found in registry"

    tool = tools[0]
    if tool.handler is None:
        return f"Error: skill '{skill_name}' has no handler"

    output, success = await tool.handler(arguments)
    if not success:
        return f"Error executing {skill_name}: {output}"

    structured = _extract_json_from_markdown(output)
    if structured:
        output += f"\n\n<!-- JSON: {json.dumps(structured, default=str)} -->"

    return output


# Module-level server instance (created lazily)
_server: FastMCP | None = None


def get_mcp_server() -> "FastMCP":
    """Get or create the singleton MCP server."""
    global _server
    if _server is None:
        _server = _create_mcp_server()
        _register_all_tools(_server)
    return _server


def start_mcp_server(transport: str = "stdio"):
    """Start the MCP server.

    Args:
        transport: 'stdio' for stdin/stdout (Claude Desktop, Claude Code),
                   'sse' for Server-Sent Events (web clients)
    """
    server = get_mcp_server()
    server.run(transport=transport)


# ── Legacy compatibility ──

class MCPServer:
    """Legacy MCP server wrapper for backward compatibility.

    New code should use get_mcp_server() or start_mcp_server() instead.
    """

    def __init__(self):
        self._tools = self._build_tool_list()

    def _build_tool_list(self) -> dict:
        from supplymind.agent.tools import create_supplymind_tools
        tools = create_supplymind_tools()
        return {t.name: t for t in tools}

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            loop = asyncio.new_event_loop()
            output, success = loop.run_until_complete(tool.handler(arguments or {}))
            loop.close()
            return {"success": success, "tool": name, "result": output}
        except Exception as e:
            return {"success": False, "tool": name, "error": str(e)}

    def handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.list_tools()}}
        elif method == "tools/call":
            result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    def start_stdio_server(self):
        if _MCP_AVAILABLE:
            start_mcp_server("stdio")
        else:
            import sys
            logger.info("MCP SDK not available, using legacy JSON-RPC mode")
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    response = self.handle_request(request)
                    print(json.dumps(response, ensure_ascii=False, default=str))
                    sys.stdout.flush()
                except json.JSONDecodeError as e:
                    print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}))
                    sys.stdout.flush()
