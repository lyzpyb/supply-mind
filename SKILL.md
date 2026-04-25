---
name: "supplymind"
description: "Supply chain intelligence toolkit for AI agents. Provides demand forecasting, inventory optimization, pricing strategy, and fulfillment planning capabilities. Use this when the user needs supply chain analysis, demand planning, inventory decisions, pricing recommendations, or logistics optimization."
tags:
  - "supply-chain"
  - "demand-planning"
  - "inventory"
  - "pricing"
  - "fulfillment"
  - "operations-research"
---

# SupplyMind — Supply Chain Intelligence for AI Agents

SupplyMind is a comprehensive supply chain analysis toolkit that exposes **20+ specialized tools** for AI agents. It follows the HuggingFace ml-intern ToolSpec pattern, where each capability is a self-describing tool with structured inputs and markdown-formatted outputs.

## When to Use SupplyMind

Engage SupplyMind when the user's request involves:

- **Demand Planning**: Forecasting future demand, detecting anomalies, new product launches
- **Inventory Management**: Reorder points, safety stock, policy simulation, ABC classification
- **Pricing Strategy**: Elasticity estimation, markdown optimization, lifecycle pricing, bundling
- **Fulfillment & Logistics**: Inventory allocation, route optimization, wave planning, capacity analysis
- **Data Quality**: Profiling and cleaning supply chain datasets
- **Decision Support**: What-if scenario comparison across multiple strategies

## Quick Start

All tools are available through the `ToolRouter`. Basic usage pattern:

```python
from supplymind.agent import get_tool_router

# Create router with all tools pre-registered
router = get_tool_router()

# Get OpenAI function-calling format (for LLM consumption)
specs = router.get_tool_specs_for_llm()

# Execute a tool
output, success = await router.call_tool("demand_forecast", {
    "demand_history": [
        {"sku_id": "SKU001", "quantity": 100, "date": "2025-01-01"},
        {"sku_id": "SKU001", "quantity": 120, "date": "2025-01-02"},
        # ... more records
    ],
    "horizon": 14,
    "method": "auto",
})
```

## Available Tools

### 🔍 Common Tools

| Tool | Description | Key Input |
|------|-------------|-----------|
| `data_profiler` | Profile data quality, detect issues | `data` (array of records) |
| `report_generator` | Generate formatted analysis reports | `title`, `sections` |
| `what_if` | Multi-scenario decision simulation | `base_scenario`, `scenarios` |

### 📈 Demand Tools

| Tool | Description | Key Input |
|------|-------------|-----------|
| `demand_forecast` | **Primary forecast** with confidence intervals | `demand_history`, `horizon` |
| `demand_decompose` | Trend/seasonal/residual decomposition | `demand_history` |
| `demand_anomaly` | Detect outliers and anomalies | `demand_history`, `sensitivity` |
| `demand_newproduct` | New product launch forecasting | `product_attributes`, `reference_products` |
| `demand_intermittent` | Sparse/lumpy demand (Croston) | `demand_history`, `service_level` |
| `demand_reconcile` | Bottom-up / top-down reconciliation | `detailed_forecasts`, `aggregated_targets` |

### 📦 Inventory Tools

| Tool | Description | Key Input |
|------|-------------|-----------|
| `inventory_reorder` | EOQ + reorder point calculation | `skus`, `service_level_target` |
| `inventory_safety_stock` | Safety stock for service levels | `skus`, `service_level` |
| `inventory_policy_sim` | Monte Carlo policy comparison | `sku_params`, `policies` |
| `inventory_classify` | ABC-XYZ segmentation | `sku_data` |
| `inventory_multi_echelon` | Multi-tier network optimization | `network`, `demand_at_nodes` |
| `inventory_newsvendor` | Perishable/seasonal optimal qty | `product` (price/cost/demand) |

### 💰 Pricing Tools

| Tool | Description | Key Input |
|------|-------------|-----------|
| `pricing_elasticity` | Price sensitivity estimation | `prices`, `quantities` |
| `pricing_markdown` | Clearance/Markdown optimization | `current_price`, `cost`, `inventory_remaining`, `days_left` |
| `pricing_lifecycle` | Stage detection + pricing strategy | `sales_history`, `price_history` |
| `pricing_bundling` | Bundle recommendation + pricing | `transactions`, `sku_prices` |

### 🚚 Fulfillment Tools

| Tool | Description | Key Input |
|------|-------------|-----------|
| `fulfill_allocation` | Multi-source inventory allocation | `inventory_positions`, `demands` |
| `fulfill_routing` | TSP route optimization | `depot`, `stops` |
| `fulfill_wave` | Warehouse wave picking plan | `orders`, `warehouse_config` |
| `fulfill_capacity` | Capacity bottleneck analysis | `demand_plan`, `capacity_resources` |

## Typical Workflows

### Workflow 1: Demand Planning Cycle

```
1. data_profiler     → Validate incoming demand data quality
2. demand_anomaly     → Detect and flag anomalous periods
3. demand_forecast    → Generate baseline forecasts
4. demand_decompose   → Understand trend/seasonality drivers
5. what_if            → Compare scenarios (promotion vs baseline)
```

### Workflow 2: Inventory Optimization

```
1. inventory_classify → Segment SKUs by ABC-XYZ
2. demand_forecast    → Get demand projections
3. inventory_reorder  → Calculate R,Q parameters
4. inventory_policy_sim → Test policies with Monte Carlo
5. what_if           → Compare 90% vs 95% vs 99% service levels
```

### Workflow 3: Pricing Decision

```
1. pricing_elasticity → Measure price sensitivity
2. pricing_lifecycle  → Identify product stage
3. pricing_markdown    → If decline stage: optimize clearance
4. pricing_bundling    → Find cross-sell opportunities
5. what_if            → Compare -10%, -20%, -30% price scenarios
```

### Workflow 4: Fulfillment Planning

```
1. fulfill_capacity   → Check if network can handle demand
2. fulfill_allocation → Allocate constrained inventory
3. fulfill_routing    → Optimize delivery routes
4. fulfill_wave       → Plan warehouse picking waves
```

## Input Data Format

Most tools accept flexible input formats. The standard demand record format is:

```json
{
  "sku_id": "string — product identifier",
  "quantity": "number — units demanded/sold",
  "date": "string — YYYY-MM-DD",
  "location_id": "string — optional warehouse/store",
  "sku_name": "string — optional human-readable name",
  "category": "string — optional product category"
}
```

**Data flexibility**: All tools handle:
- Missing optional fields (auto-filled with defaults)
- Both list-of-dicts and wrapped `{"demand_history": [...]}` formats
- Sparse data (not all fields need to be present in every record)

## Output Format

Every tool returns a tuple of `(markdown_string, success_bool)`:

- **On success**: Formatted markdown report with tables, metrics, and insights
- **On error**: Descriptive error message with troubleshooting hints

The markdown output is designed to be:
- Human-readable for direct display
- Structured enough for LLM parsing and follow-up actions
- Includes JSON block with full result data for programmatic use

## Integration Patterns

### LangChain Integration

```python
from supplymind.adapters.langchain_tool import get_all_tools
tools = get_all_tools()  # Returns LangChain BaseTool instances
agent = create_react_agent(llm, tools, prompt)
```

### MCP Server Integration

SupplyMind's built-in MCP server at `supplymind.mcp.server` exposes tools as JSON-RPC endpoints.

### Direct Python API

```python
from supplymind.skills.demand.forecast.main import DemandForecast
from supplymind.skills.demand.forecast.schema import ForecastInput

skill = DemandForecast()
result = skill.run(ForecastInput(
    demand_history=[...],
    horizon=14,
))
```

## Architecture Notes

- **Core algorithms** live in `supplymind/core/` (pure math, no I/O)
- **Skill wrappers** live in `supplymind/skills/{domain}/{name}/` (schema + logic + CLI)
- **Agent layer** lives in `supplymind/agent/` (ToolSpec registry + async handlers)
- **Adapters** live in `supplymind/adapters/` (LangChain, MCP, etc.)

Each skill follows a consistent internal structure:
```
skills/{domain}/{name}/
├── schema.py    # Pydantic Input/Output models
├── main.py      # Skill class with .run() method  
└── cli.py       # Click command-line interface
```
