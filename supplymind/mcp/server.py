"""
MCP Server — exposes SupplyMind capabilities via Model Context Protocol.

Provides tools for AI assistants (Claude, GPT, etc.) to call
SupplyMind skills directly through the MCP protocol.

Tools available:
  - demand_forecast: Generate demand forecasts
  - demand_decompose: Decompose time series into trend/seasonal/residual
  - inventory_classify: ABC-XYZ classification
  - inventory_reorder: Generate reorder suggestions
  - safety_stock: Calculate safety stock levels
  - data_profiler: Profile and analyze input data
  - run_pipeline: Execute a full pipeline from YAML definition
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


class MCPServer:
    """Lightweight MCP-compatible server for SupplyMind.

    Implements a tool-calling interface that can be wrapped by any MCP SDK.
    Uses a simple JSON-RPC-like protocol over stdio or HTTP.
    """

    def __init__(self):
        self._tools = self._register_tools()
        logger.info(f"MCP Server initialized with {len(self._tools)} tools")

    def _register_tools(self) -> dict:
        """Register all available MCP tools."""
        return {
            "demand_forecast": {
                "description": "Generate demand forecasts using statistical models. Supports auto method selection, Holt-Winters, Croston's method, etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "demand_history": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Demand records with sku_id, date, quantity fields",
                        },
                        "horizon": {"type": "integer", "default": 14, "description": "Forecast horizon in days"},
                        "method": {
                            "type": "string",
                            "enum": ["auto", "ma", "ema", "holt_winters", "croston"],
                            "default": "auto",
                        },
                        "confidence_level": {"type": "number", "default": 0.95},
                    },
                    "required": ["demand_history"],
                },
                "handler": self._handle_demand_forecast,
            },
            "demand_decompose": {
                "description": "Decompose a time series into trend, seasonal, and residual components using STL decomposition.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "demand_history": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Demand records with sku_id, date, quantity fields",
                        },
                        "period": {"type": "integer", "description": "Seasonal period (auto-detect if omitted)"},
                    },
                    "required": ["demand_history"],
                },
                "handler": self._handle_demand_decompose,
            },
            "inventory_classify": {
                "description": "Perform ABC-XYZ matrix classification on SKUs based on revenue value and demand variability.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Item list with item_id, revenue, demand_values fields",
                        },
                    },
                    "required": ["items"],
                },
                "handler": self._handle_inventory_classify,
            },
            "inventory_reorder": {
                "description": "Generate reorder suggestions including order quantities, timing, and reasoning.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sku_id": {"type": "string"},
                        "current_inventory": {"type": "number"},
                        "demand_forecast": {"type": "array", "items": {"type": "number"}},
                        "lead_time_days": {"type": "number", "default": 7},
                        "service_level": {"type": "number", "default": 0.95},
                    },
                    "required": ["sku_id", "current_inventory", "demand_forecast"],
                },
                "handler": self._handle_reorder,
            },
            "safety_stock": {
                "description": "Calculate optimal safety stock using service level or Monte Carlo methods.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "demand_std": {"type": "number", "description": "Daily demand standard deviation"},
                        "lead_time_mean": {"type": "number", "description": "Mean lead time in days"},
                        "target_service_level": {"type": "number", "default": 0.95},
                        "method": {"type": "string", "enum": ["service_level", "monte_carlo"], "default": "service_level"},
                    },
                    "required": ["demand_std", "lead_time_mean"],
                },
                "handler": self._handle_safety_stock,
            },
            "data_profiler": {
                "description": "Profile and analyze input data to detect patterns, quality issues, and characteristics.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "array", "items": {"type": "object"}},
                        "profile_type": {"type": "string", "enum": ["full", "quick"], "default": "quick"},
                    },
                    "required": ["data"],
                },
                "handler": self._handle_data_profiler,
            },
            "run_pipeline": {
                "description": "Execute a full SupplyMind pipeline from a YAML definition file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pipeline_path": {"type": "string", "description": "Path to pipeline YAML file"},
                        "data_path": {"type": "string", "description": "Path to input data file"},
                    },
                    "required": ["pipeline_path"],
                },
                "handler": self._handle_run_pipeline,
            },
            # Phase 3: Pricing tools
            "pricing_elasticity": {
                "description": "Estimate price elasticity using log-log OLS regression. Returns elasticity coefficient, classification, and revenue-optimal price.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prices": {"type": "array", "items": {"type": "number"}, "description": "Historical prices"},
                        "quantities": {"type": "array", "items": {"type": "number"}, "description": "Corresponding quantities sold"},
                    },
                    "required": ["prices", "quantities"],
                },
                "handler": self._handle_pricing_elasticity,
            },
            "pricing_markdown": {
                "description": "Optimize phased markdown (clearance) pricing strategy under time pressure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "current_stock": {"type": "number", "description": "Units on hand to clear"},
                        "unit_cost": {"type": "number", "description": "Per-unit cost"},
                        "original_price": {"type": "number", "description": "Current/list price"},
                        "elasticity": {"type": "number", "default": -2.0},
                        "days_remaining": {"type": "integer", "default": 30},
                    },
                    "required": ["current_stock", "unit_cost", "original_price"],
                },
                "handler": self._handle_pricing_markdown,
            },
            "pricing_lifecycle": {
                "description": "Detect product lifecycle stage (introduction/growth/maturity/decline) and recommend pricing strategy.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "weekly_sales": {"type": "array", "items": {"type": "number"}, "description": "Weekly sales volumes"},
                        "weeks_since_launch": {"type": "integer"},
                    },
                    "required": ["weekly_sales"],
                },
                "handler": self._handle_pricing_lifecycle,
            },
            # Phase 3: Fulfillment tools
            "fulfill_routing": {
                "description": "Solve TSP route optimization using nearest neighbor + 2-opt improvement.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "locations": {"type": "array", "items": {"type": "object"}, "description": "Locations with lat, lon, demand"},
                        "vehicle_capacity": {"type": "number", "default": 1000.0},
                    },
                    "required": ["locations"],
                },
                "handler": self._handle_fulfill_routing,
            },
            "what_if": {
                "description": "Run multi-scenario what-if simulation comparing different parameter sets side by side.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "base_params": {"type": "object", "description": "Base parameters for simulation"},
                        "scenarios": {"type": "array", "items": {"type": "object"}, "description": "Scenario definitions with name and params"},
                        "skill_name": {"type": "string", "default": "inventory-policy-sim"},
                    },
                    "required": ["base_params", "scenarios"],
                },
                "handler": self._handle_what_if,
            },
        }

    # ── Tool Handlers ──

    def _handle_demand_forecast(self, arguments: dict) -> dict:
        from supplymind.skills.demand.forecast.main import DemandForecast
        from supplymind.skills.demand.forecast.schema import ForecastInput

        params = ForecastInput(**arguments)
        skill = DemandForecast()
        result = skill.run(params)
        return result.model_dump()

    def _handle_demand_decompose(self, arguments: dict) -> dict:
        from supplymind.skills.demand.decompose.main import DemandDecompose
        from supplymind.skills.demand.decompose.schema import DecomposeInput

        params = DecomposeInput(**arguments)
        skill = DemandDecompose()
        result = skill.run(params)
        return result.model_dump()

    def _handle_inventory_classify(self, arguments: dict) -> dict:
        from supplymind.core.classification import abc_xyz_matrix

        items = arguments.get("items", [])
        result = abc_xyz_matrix(items)
        # Convert to serializable format
        output = {
            "summary": result.summary,
            "matrix": {},
        }
        for label, cell in result.matrix.items():
            output["matrix"][label] = {
                "item_ids": cell.item_ids,
                "count": cell.count,
                "total_value": cell.total_value,
                "strategy": cell.strategy,
            }
        return output

    def _handle_reorder(self, arguments: dict) -> dict:
        from supplymind.skills.inventory.reorder.main import InventoryReorder
        from supplymind.skills.inventory.reorder.schema import ReorderInput

        params = ReorderInput(
            sku_id=arguments["sku_id"],
            current_inventory=arguments["current_inventory"],
            demand_forecast=arguments.get("demand_forecast", []),
            lead_time_days=arguments.get("lead_time_days", 7),
            target_service_level=arguments.get("service_level", 0.95),
        )
        skill = InventoryReorder()
        result = skill.run(params)
        return result.model_dump()

    def _handle_safety_stock(self, arguments: dict) -> dict:
        from supplymind.core.inventory_models import ss_service_level_full, ss_stochastic

        method = arguments.get("method", "service_level")
        if method == "monte_carlo":
            result = ss_stochastic(
                demand_std=arguments["demand_std"],
                lead_time_mean=arguments["lead_time_mean"],
                target_service_level=arguments.get("target_service_level", 0.95),
            )
        else:
            result = ss_service_level_full(
                demand_mean_daily=100.0,  # Approximate
                std_demand_daily=arguments["demand_std"],
                lead_time_mean_days=arguments["lead_time_mean"],
                std_lead_time_days=0.0,
                target_service_level=arguments.get("target_service_level", 0.95),
            )

        return {
            "safety_stock": round(result.safety_stock, 2),
            "reorder_point": round(result.reorder_point, 2),
            "service_level_achieved": result.service_level_achieved,
            "method": result.method,
        }

    def _handle_data_profiler(self, arguments: dict) -> dict:
        from supplymind.skills.common.data_profiler.main import DataProfiler
        from supplymind.skills.common.data_profiler.schema import ProfilerInput

        data_arg = arguments.get("data", {})
        # Accept both dict (wrapped) and list (raw demand records)
        if isinstance(data_arg, list):
            data_input = {"demand_history": data_arg}
        else:
            data_input = data_arg if isinstance(data_arg, dict) else {}
        params = ProfilerInput(data=data_input)
        skill = DataProfiler()
        result = skill.run(params)
        return result.model_dump()

    def _handle_run_pipeline(self, arguments: dict) -> dict:
        from supplymind.pipelines.engine import PipelineEngine

        engine = PipelineEngine(
            pipeline_path=arguments["pipeline_path"],
            data_path=arguments.get("data_path"),
        )
        result = engine.run()
        return {
            "name": result.name,
            "status": result.status.value,
            "completed_steps": result.completed_steps,
            "total_steps": result.total_steps,
            "duration_seconds": round(result.duration_seconds, 2),
            "output_summary": result.output_summary,
            "errors": result.errors,
        }

    def _handle_pricing_elasticity(self, arguments: dict) -> dict:
        from supplymind.skills.pricing.elasticity.main import PricingElasticity
        from supplymind.skills.pricing.elasticity.schema import ElasticityInput

        params = ElasticityInput(**arguments)
        skill = PricingElasticity()
        result = skill.run(params)
        return result.model_dump()

    def _handle_pricing_markdown(self, arguments: dict) -> dict:
        from supplymind.skills.pricing.markdown.main import PricingMarkdown
        from supplymind.skills.pricing.markdown.schema import MarkdownInput

        params = MarkdownInput(**arguments)
        skill = PricingMarkdown()
        result = skill.run(params)
        return result.model_dump()

    def _handle_pricing_lifecycle(self, arguments: dict) -> dict:
        from supplymind.skills.pricing.lifecycle.main import PricingLifecycle
        from supplymind.skills.pricing.lifecycle.schema import LifecycleInput

        params = LifecycleInput(**arguments)
        skill = PricingLifecycle()
        result = skill.run(params)
        return result.model_dump()

    def _handle_fulfill_routing(self, arguments: dict) -> dict:
        from supplymind.skills.fulfillment.routing.main import FulfillmentRouting
        from supplymind.skills.fulfillment.routing.schema import RoutingInput

        params = RoutingInput(**arguments)
        skill = FulfillmentRouting()
        result = skill.run(params)
        return result.model_dump()

    def _handle_what_if(self, arguments: dict) -> dict:
        from supplymind.skills.common.what_if.main import WhatIfSimulator
        from supplymind.skills.common.what_if.schema import WhatIfInput

        params = WhatIfInput(**arguments)
        skill = WhatIfSimulator()
        result = skill.run(params)
        return result.model_dump()

    # ── Public API ──

    def list_tools(self) -> list[dict]:
        """List all available tools with their schemas."""
        tools = []
        for name, spec in self._tools.items():
            tools.append({
                "name": name,
                "description": spec["description"],
                "input_schema": spec["input_schema"],
            })
        return tools

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Call a tool by name with given arguments."""
        if name not in self._tools:
            return {
                "success": False,
                "tool": name,
                "error": f"Unknown tool: {name}. Available: {list(self._tools.keys())}",
            }

        try:
            handler = self._tools[name]["handler"]
            result = handler(arguments or {})
            return {
                "success": True,
                "tool": name,
                "result": result,
            }
        except Exception as e:
            logger.error(f"Tool '{name}' error: {e}\n{traceback.format_exc()}")
            return {
                "success": False,
                "tool": name,
                "error": f"{type(e).__name__}: {str(e)}",
            }

    def handle_request(self, request: dict) -> dict:
        """Handle an incoming MCP-style request.

        Request format:
        {
            "jsonrpc": "2.0",
            "method": "tools/list" | "tools/call",
            "id": <request_id>,
            "params": {...}
        }
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.list_tools()}}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            result = self.call_tool(tool_name, args)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def start_stdio_server(self):
        """Start an MCP server reading JSON-RPC from stdin, writing to stdout."""
        import sys

        logger.info("MCP stdio server starting...")
        sys.stderr.write("SupplyMind MCP Server running (stdio mode)\n")
        sys.stderr.flush()

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
                error_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
                print(json.dumps(error_resp))
                sys.stdout.flush()


# Convenience function for CLI entry point
def start_mcp_server(transport: str = "stdio"):
    """Start the MCP server.

    Args:
        transport: 'stdio' for stdin/stdout, 'http' for HTTP server
    """
    server = MCPServer()

    if transport == "stdio":
        server.start_stdio_server()
    elif transport == "http":
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse

        class MCPHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                try:
                    request = json.loads(body)
                    response = server.handle_request(request)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response, ensure_ascii=False, default=str).encode())
                except Exception as e:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())

            def do_GET(self):
                if self.path == "/tools":
                    response = {"tools": server.list_tools()}
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress default logging

        httpd = HTTPServer(('127.0.0.1', 8765), MCPHandler)
        logger.info("MCP HTTP server starting on http://127.0.0.1:8765")
        print("SupplyMind MCP Server running on http://127.0.0.1:8765")
        httpd.serve_forever()
    else:
        raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'.")
