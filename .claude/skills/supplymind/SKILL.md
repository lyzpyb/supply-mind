---
name: supplymind
description: "Provides 20+ supply chain analysis tools for AI agents including demand forecasting, inventory optimization, pricing strategy, fulfillment planning, data profiling, and what-if simulation. Use when the user needs supply chain analysis, demand planning, inventory decisions, pricing recommendations, logistics optimization, sales forecasting, stock management, or operations research. Triggers on keywords: supply chain, demand forecast, inventory, safety stock, reorder, pricing, elasticity, markdown, routing, allocation, ABC-XYZ, newsvendor, TSP, wave picking, capacity planning, replenishment."
allowed-tools:
  - "Bash"
  - "Read"
  - "Write"
---

# SupplyMind — Supply Chain Intelligence Toolkit

SupplyMind is a **pure Python** supply chain analysis framework. All tools are executed via CLI commands through `python -m supplymind <command>`.

## Prerequisites

Ensure SupplyMind is installed in the current Python environment:

```bash
pip install -e /path/to/supply-mind
# or if already installed:
python -m supplymind --help
```

Core dependencies (auto-installed): numpy, pandas, scipy, pydantic, click, pyyaml

## How to Execute Tools

Every tool is a **CLI command**. Run via Bash:

```bash
python -m supplymind <tool-name> [options]
```

### Quick Reference — All 22 Tools

#### 🔍 Data & Reporting

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `data-profiler` | Profile data quality & statistics | `--input FILE` |
| `report-generator` | Generate Markdown/HTML reports | `--title STR`, `--input FILE` |
| `what-if` | Multi-scenario simulation | `-s SCENARIOS_JSON` |

#### 📈 Demand Planning

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `demand-forecast` | Forecast with confidence intervals | `--input FILE`, `--horizon N`, `--method auto\|ma\|ema\|holt_winters\|croston` |
| `demand-decompose` | STL trend/seasonal/residual decomposition | `--input FILE`, `--period N` |
| `demand-anomaly` | Detect outliers & clean data | `--input FILE`, `--sensitivity FLOAT` |
| `demand-newproduct` | New product launch forecast | `--sku-id STR`, `--category STR` |
| `demand-intermittent` | Sparse/lumpy demand (Croston) | `--input FILE`, `--variant sba\|tsb` |
| `demand-reconcile` | Bottom-up / top-down reconciliation | `--input FILE`, `method bottom_up\|top_down` |

#### 📦 Inventory Management

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `inventory-classify` | ABC-XYZ segmentation | `--input FILE` |
| `inventory-safety-stock` | Safety stock calculation | `--input FILE` |
| `inventory-reorder` | EOQ + reorder point suggestions | `--input FILE` |
| `inventory-policy-sim` | Monte Carlo policy comparison | `--sku-id STR`, `--demand-mean FLOAT` |
| `inventory-multi-echelon` | Multi-tier network optimization | `--config FILE` |
| `inventory-newsvendor` | Perishable/seasonal optimal qty | `--price FLOAT`, `--cost FLOAT` |

#### 💰 Pricing Strategy

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `pricing-elasticity` | Price sensitivity estimation | `-p "PRICE_LIST"`, `-q "QTY_LIST"` |
| `pricing-markdown` | Clearance/Markdown optimization | `--stock INT`, `--cost FLOAT`, `--price FLOAT`, `--days INT` |
| `pricing-lifecycle` | Stage detection + pricing advice | `-s "SALES_LIST"` |
| `pricing-bundling` | Bundle recommendation + pricing | `-t TRANSACTIONS_FILE` |

#### 🚚 Fulfillment & Logistics

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `fulfill-allocation` | Multi-source inventory allocation | `-o ORDERS_FILE`, `-i INVENTORY_FILE` |
| `fulfill-routing` | TSP route optimization | `-l LOCATIONS_FILE` |
| `fulfill-wave` | Warehouse wave picking plan | `-o ORDERS_FILE` |
| `fulfill-capacity` | Capacity bottleneck analysis | `-r RESOURCES_FILE` |

#### 🔧 Orchestration

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `run-pipeline` | Execute YAML pipeline | `-p PIPELINE_YAML`, `-d DATA_FILE` |
| `dashboard` | Start web dashboard | `--host ADDR`, `--port PORT` |

## Typical Workflows

### Workflow 1: Demand Planning Cycle

```bash
# Step 1: Profile incoming data
python -m supplymind data-profiler --input datasets/retail_grocery/sample_demand.csv

# Step 2: Detect anomalies
python -m supplymind demand-anomaly --input datasets/retail_grocery/sample_demand.csv

# Step 3: Generate forecast
python -m supplymind demand-forecast --input datasets/retail_grocery/sample_demand.csv --horizon 14

# Step 4: Decompose to understand drivers
python -m supplymind demand-decompose --input datasets/retail_grocery/sample_demand.csv --period 7

# Step 5: Compare scenarios
python -m supplymind what-if -s scenarios.json
```

### Workflow 2: Inventory Optimization

```bash
# Step 1: Classify SKUs by ABC-XYZ
python -m supplymind inventory-classify --input items.json

# Step 2: Calculate safety stock
python -m supplymind inventory-safety-stock --input items.json

# Step 3: Generate reorder suggestions
python -m supplymind inventory-reorder --input forecast.json

# Step 4: Simulate different policies
python -m supplymind inventory-policy-sim --sku-id SKU001 --demand-mean 150

# Step 5: Compare service levels via what-if
python -m supplymind what-if -s service_level_scenarios.json
```

### Workflow 3: Pricing Decision

```bash
# Step 1: Measure price sensitivity
python -m supplymind pricing-elasticity -p "9.99,8.99,7.99" -q "100,130,170"

# Step 2: Identify lifecycle stage
python -m supplymind pricing-lifecycle -s "10,15,22,35,48,55,60,58,52,45"

# Step 3: If decline stage → optimize clearance
python -m supplymind pricing-markdown --stock 500 --cost 5.0 --price 19.99 --days 14

# Step 4: Find bundle opportunities
python -m supplymind pricing-bundling -t transactions.json
```

### Workflow 4: Full Pipeline (One Command)

```bash
python -m supplymind run-pipeline pipelines/retail-replenish.yaml --data datasets/retail_grocery/sample_demand.csv
```

## Input Data Format

Most tools accept CSV or JSON input. The standard demand record format:

```csv
sku_id,date,quantity,location_id
SKU001,2025-01-01,100,WH_A
SKU001,2025-01-02,120,WH_A
```

JSON format is also accepted for most tools.

## Output Format

All tools output **structured text** (tables, metrics) to stdout. Results are human-readable and suitable for summarizing back to the user.

## Error Handling

If a tool fails:
1. Check that input file exists and has correct format
2. Ensure all required options are provided (`--help` shows full options)
3. Verify dependencies: `pip install numpy pandas scipy pydantic click pyyaml`

## Additional Resources

- For complete API details and Python integration, see [SKILL.md](../../SKILL.md)
- For algorithm documentation, see README.md
