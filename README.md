<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License" />
  <img src="https://img.shields.io/badge/Tests-231%20passing-brightgreen.svg" alt="Tests" />
  <img src="https://img.shields.io/badge/Skills-20%2B-tools-orange.svg" alt="Skills" />
  <a href="#english"><img src="https://img.shields.io/badge/lang-English-gray.svg" /></a>
  <a href="#中文"><img src="https://img.shields.io/badge/lang-中文版-red.svg" /></a>
</p>

<h1 align="center">SupplyMind</h1>

<p align="center">
  <strong>Self-improving, Skill-based Supply Chain Planning Agent Framework with Human-in-the-Loop</strong>
</p>

<p align="center">
  不做平台，做供应链的瑞士军刀 🔗🧠
</p>

---

## ✨ 核心特点

| 特性 | 说明 |
|------|------|
| 🧩 **Skill-based** | 每个能力是一个独立 Skill，即插即用，可单独运行 |
| 🤖 **Agent-Ready** | **20+ tools** 原生支持 Claude Code / CatPaw / LangChain / MCP，零配置即插即用 |
| 🧠 **Self-improving** | 内置 Memory 系统 + Learning Loop，越用越懂你的业务 |
| 👤 **Human-in-the-loop** | 三级人机协作（Auto / Review / Collaborate），关键决策人类拍板 |
| 📊 **Observable** | 轻量 Dashboard 实时观察 Pipeline 状态和结果 |
| 🔌 **Framework-agnostic** | 零框架依赖，纯 Python + CLI，可接入任意 Agent 框架 |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/lyzpyb/supply-mind.git
cd supply-mind

# Install (only 6 core dependencies)
pip install numpy pandas scipy pydantic click pyyaml

# Run CLI
python -m supplymind --help

# Run a single Skill
python -m supplymind data-profiler --input datasets/retail_grocery/sample_demand.csv

# Run demand forecast
python -m supplymind demand-forecast --input datasets/retail_grocery/sample_demand.csv --horizon 14

# Run full pipeline
python -m supplymind run-pipeline pipelines/retail-replenish.yaml --data datasets/retail_grocery/sample_demand.csv

# Start dashboard
python -m supplymind dashboard
```

### 🤖 Use as Agent Tools (NEW)

SupplyMind skills can be used directly by any AI agent framework:

```python
from supplymind.agent import get_tool_router

# Create router with all 20+ supply chain tools
router = get_tool_router()

# Get OpenAI function-calling format → pass to any LLM
specs = router.get_tool_specs_for_llm()

# Execute a tool
output, success = await router.call_tool("demand_forecast", {
    "demand_history": [
        {"sku_id": "SKU001", "quantity": 100, "date": "2025-01-01"},
        # ... more records
    ],
    "horizon": 14,
    "method": "auto",
})
# output = markdown-formatted analysis report ✨
```

Also works with LangChain:
```python
from supplymind.adapters.langchain_tool import get_all_tools
tools = get_all_tools()  # LangChain BaseTool instances
```

See [SKILL.md](SKILL.md) for the complete agent-facing skill description.

## 📐 Architecture

SupplyMind 采用四层架构设计：

```
╔═══════════════════════════════════════════════════════════════════╗
║                   Layer 4: Agent Toolkit 🆕                     ║
║   ToolSpec Registry │ Async Handlers │ OpenAI Format Export     ║
╠═══════════════════════════════════════════════════════════════════╣
║                   Layer 3: Intelligence                         ║
║   Learning Loop │ Memory System │ User Modeling │ Evolution     ║
╠═══════════════════════════════════════════════════════════════════╣
║                   Layer 2: Interaction                           ║
║   HITL Engine (3-level) │ Live Dashboard │ Pipeline Builder      ║
╠═══════════════════════════════════════════════════════════════════╣
║                   Layer 1: Capabilities                          ║
║   Demand │ Inventory │ Pricing │ Fulfillment │ Common           ║
║   ─────────────────────────────────────────────────────────────  ║
║        Algorithm Engine (core/)  +  Data Protocol (protocol/)    ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Layer 4: Agent Toolkit 🆕

参考 HuggingFace ml-intern 的 ToolSpec/ToolRouter 模式实现。每个 Skill 暴露为标准化的 Agent Tool：

| Domain | Tools | Description |
|--------|-------|-------------|
| 🔍 **Common** | `data_profiler`, `report_generator`, `what_if` | Data quality, reports, scenario simulation |
| 📈 **Demand** | `demand_forecast`, `demand_decompose`, `demand_anomaly`, `demand_newproduct`, `demand_intermittent`, `demand_reconcile` | Full demand planning lifecycle |
| 📦 **Inventory** | `inventory_reorder`, `inventory_safety_stock`, `inventory_policy_sim`, `inventory_classify`, `inventory_multi_echelon`, `inventory_newsvendor` | EOQ, safety stock, ABC-XYZ, newsvendor |
| 💰 **Pricing** | `pricing_elasticity`, `pricing_markdown`, `pricing_lifecycle`, `pricing_bundling` | Elasticity, markdown, lifecycle, bundles |
| 🚚 **Fulfillment** | `fulfill_allocation`, `fulfill_routing`, `fulfill_wave`, `fulfill_capacity` | Allocation, TSP routing, wave picking, capacity |

**Architecture pattern (ml-intern style):**
```
TOOL_SPEC dict          ← LLM sees: name + description + JSON Schema
    ↓
async handler(args)      ← Bridge: validates → calls skill.run() → formats markdown
    ↓
Skill.run(input)         ← Core business logic (Pydantic in/out)
    ↓
(str_output, bool_ok)    ← Return to agent loop
```

### Layer 1: Capabilities — Skills & Algorithms

#### Core Algorithm Engine (`supplymind/core/`)

| 模块 | 算法 |
|------|------|
| `timeseries.py` | Moving Average, EMA, Holt-Winters, STL Decomposition, Croston's Method, Auto Forecast |
| `inventory_models.py` | EOQ, ROP, Safety Stock (service level / stochastic), Newsvendor, (s,S) Policy Simulation |
| `pricing_models.py` | Price Elasticity (log-log regression), Markdown Optimization, Lifecycle Detection, Bundle Recommendation |
| `fulfillment_models.py` | Fair Allocation (LP), TSP Routing (NN + 2-opt), Wave Planning, Capacity Check |
| `optimization.py` | Linear Programming allocation, TSP (Nearest Neighbor + 2-opt) |
| `statistics.py` | Z-score/IQR Outlier Detection, Bootstrap CI, Coefficient of Variation |
| `classification.py` | ABC Analysis (Pareto), XYZ Classification, ABC-XYZ Matrix |

#### Skills (`supplymind/skills/`)

| Skill | 功能 | 输入 | 输出 |
|-------|------|------|------|
| `data-profiler` | 数据质量分析 & 统计摘要 | CSV/JSON | 数据画像报告 |
| `demand-forecast` | 时序需求预测（5 种方法） | 历史销量 + horizon | 逐日预测 + 置信区间 |
| `demand-decompose` | 时序分解（趋势/季节/残差） | 销售数据 | 分解组件 |
| `demand-anomaly` | 异常检测与清洗 | 销售数据 | 清洗后数据 + 异常标记 |
| `demand-newproduct` | 新品预测（类比/Bass 曲线） | 产品属性 + 参照品 | 新品预测 |
| `demand-intermittent` | 稀疏需求预测（Croston） | 零售数据 | 间歇性预测 |
| `demand-reconcile` | 预测调和（自下而上 / 自上而下） | 多层级预测 | 一致化预测 |
| `inventory-classify` | ABC-XYZ 分类 | SKU 列表 + 销量 | 3×3 矩阵分类 |
| `inventory-safety-stock` | 安全库存计算 | 需求分布 + 提前期 | 各 SKU 安全库存建议 |
| `inventory-reorder` | 补货建议生成 | 预测 + 库存 + SS | 补货清单 + 紧急度排序 |
| `inventory-policy_sim` | 库存策略仿真（蒙特卡洛） | SKU 参数 + 策略列表 | 策略对比报告 |
| `inventory-multi-echelon` | 多级库存优化 | 网络结构 + 需求 | 各节点库存策略 |
| `inventory-newsvendor` | 报童模型（易腐品） | 价格/成本/需求分布 | 最优订货量 |
| `pricing-elasticity` | 价格弹性估算 | 价格序列 + 销量序列 | 弹性系数 + 解读 |
| `pricing-markdown` | 清仓/降价优化 | 当前价/成本/库存/剩余天数 | 最优降价策略 |
| `pricing-lifecycle` | 生命周期定价 | 销售趋势 + 价格历史 | 阶段判断 + 定价建议 |
| `pricing-bundling` | 捆绑推荐 | 交易记录 + SKU 价格 | 捆绑方案 + 捆绑价 |
| `fulfill-allocation` | 库存分配 | 各仓库存 + 需求 | 分配方案 |
| `fulfill-routing` | 配送路径优化 (TSP) | 仓库 + 停靠点坐标 | 最优路径 |
| `fulfill-wave` | 波次拣货计划 | 订单列表 + 仓库配置 | 波次计划 |
| `fulfill-capacity` | 履约能力检查 | 需求计划 + 资源能力 | 瓶颈分析 |
| `what-if` | 多场景模拟 | 基准场景 + 对比场景 | 场景对比报告 |
| `report-generator` | 分析报告生成 | 任意 Skill 输出 | Markdown / HTML 报告 |

### Layer 2: Interaction — HITL & Dashboard

#### Human-in-the-Loop Engine

供应链决策不能全自动——错误的补货决策可能导致百万级损失。SupplyMind 设计三级 HITL：

| Level | 名称 | 触发条件 | 行为 |
|-------|------|----------|------|
| **Auto** | 自动执行 | 置信度 > 90%, 常规 SKU | 直接执行，事后通知 |
| **Review** | 待确认 | 置信度 60-90%, 首次品类 | 生成建议 → 等待 accept/adjust/skip |
| **Collaborate** | 协作决策 | 置信度 < 60%, 大促备货等 | 多方案对比 → 人类拍板 |

#### Dashboard

零构建、零外部依赖的 Agent 状态面板。基于 Python stdlib `http.server` + SSE 推送。

```bash
python -m supplymind dashboard    # 启动在 http://127.0.0.1:8080
```

### Layer 3: Intelligence — Memory & Learning

#### Three-Layer Memory System

```
┌─────────────────────────────────────────┐
│  Working Memory（工作记忆）             │  ← 当前会话上下文、Pipeline 中间结果
├─────────────────────────────────────────┤
│  Domain Memory（领域记忆）⭐            │  ← 数据画像、参数偏好、模型表现、异常模式
├─────────────────────────────────────────┤
│  Meta Memory（元记忆）                  │  ← Skill 使用统计、跨项目经验沉淀
└─────────────────────────────────────────┘
```

## 📊 Unified Data Protocol (UDP)

不同公司的数据格式千差万别，但供应链核心数据结构高度相似。UDP 是整个框架的基石。

**Core Schema (`supplymind/protocol/schema.py`)：**

```python
class SKUMaster(BaseModel):       # SKU 主数据
class DemandRecord(BaseModel):    # 需求记录 (sku_id, location_id, date, quantity, ...)
class InventorySnapshot(BaseModel): # 库存快照 (on_hand, in_transit, available, ...)
class LocationMaster(BaseModel):   # 位置主数据 (store/dc/factory)
class SupplyMindData(BaseModel):   # 顶层容器
```

**Data Adapter:** 支持 CSV / JSON 输入，自动映射到标准 Schema。

## 🔧 Pipeline Orchestration

Pipeline 用 YAML 定义，支持步骤编排、变量传递、HITL 检查点、错误处理：

```yaml
# pipelines/retail-replenish.yaml
name: retail-replenish
params:
  service_level: 0.95
  forecast_horizon: 14

steps:
  - skill: data-profiler
    output: $profiled
    hitl: none

  - skill: demand-anomaly
    input: $profiled
    output: $cleaned
    hitl: { level: review, timeout: 30m }

  - skill: demand-forecast
    input: $cleaned
    output: $forecast
    hitl: { level: auto }

  - skill: inventory-classify
    input: $forecast
    output: $classify

  - skill: inventory-safety-stock
    input: $classify
    output: $safety_stock

  - skill: inventory-reorder
    input: $safety_stock
    output: $reorder
    hitl: { level: collaborate, require_approval: true }

  - skill: report-generator
    input: $reorder
    output: $report
```

## 📁 Project Structure

```
supply-mind/
├── SKILL.md                       # 🆕 Agent-facing skill description
├── .claude/                        # 🆕 Claude Code native integration
│   └── skills/
│       └── supplymind/          # Claude Code Skill (auto-discovered)
│           ├── SKILL.md          # Skill definition with allowed-tools
│           └── scripts/sm.sh     # Quick runner script
├── pyproject.toml                 # Package config
├── LICENSE                       # Apache 2.0
├── README.md                     # This file
│
├── supplymind/                   # Main package
│   ├── __init__.py              # Version export
│   ├── __main__.py              # python -m supplymind entry
│   ├── cli.py                   # Click CLI (25+ subcommands)
│   │
│   ├── agent/                   # 🆕 Agent Toolkit (ml-intern pattern)
│   │   ├── __init__.py          # Exports: ToolSpec, ToolRouter, get_tool_router
│   │   ├── tools.py             # ToolSpec dataclass + ToolRouter + 20+ registry
│   │   └── skill_handlers/      # Async handler bridges (5 domain modules)
│   │       ├── common.py        # data_profiler, report_generator, what_if
│   │       ├── demand.py        # 6 demand tools
│   │       ├── inventory.py     # 6 inventory tools
│   │       ├── pricing.py       # 4 pricing tools
│   │       └── fulfillment.py   # 4 fulfillment tools
│   │
│   ├── adapters/                # Framework adapters
│   │   └── langchain_tool.py    # LangChain BaseTool wrapper
│   │
│   ├── core/                    # Algorithm engine (pure Python)
│   │   ├── timeseries.py        # MA, EMA, HW, STL, Croston
│   │   ├── inventory_models.py  # EOQ, ROP, SS, Newsvendor, (s,S)
│   │   ├── pricing_models.py    # Elasticity, Markdown, Lifecycle, Bundling
│   │   ├── fulfillment_models.py# Allocation, TSP, Wave, Capacity
│   │   ├── optimization.py      # LP, TSP, 2-opt
│   │   ├── statistics.py        # Outlier detection, bootstrap, CV
│   │   └── classification.py    # ABC, XYZ, ABC-XYZ matrix
│   │
│   ├── protocol/               # Data protocol
│   │   ├── schema.py           # Pydantic models (SKUMaster, DemandRecord, ...)
│   │   ├── adapter.py          # CSV/JSON → UDP loader
│   │   └── validators.py       # Data quality checks
│   │
│   ├── skills/                 # Business skills (22 skills)
│   │   ├── common/             # data_profiler, report_generator, what_if
│   │   ├── demand/             # forecast, decompose, anomaly, newproduct, intermittent, reconcile
│   │   ├── inventory/          # classify, safety_stock, reorder, policy_sim, multi_echelon, newsvendor
│   │   ├── pricing/            # elasticity, markdown, lifecycle, bundling
│   │   └── fulfillment/        # allocation, routing, wave, capacity
│   │
│   ├── pipelines/              # Pipeline engine
│   │   └── engine.py           # YAML executor with HITL integration
│   │
│   ├── memory/                 # Memory system
│   │   ├── working.py          # Session-level memory
│   │   ├── domain.py           # Project-level domain memory
│   │   ├── meta.py             # Agent-level meta memory
│   │   └── store.py            # JSON file store backend
│   │
│   ├── hitl/                   # Human-in-the-Loop
│   │   ├── engine.py           # 3-level approval system
│   │   ├── confidence.py       # Confidence scoring
│   │   └── feedback.py          # Feedback collector
│   │
│   ├── mcp/                    # MCP Server (Claude Code compatible)
│   │   └── server.py           # JSON-RPC tool server
│   │
│   └── dashboard/              # Web UI
│       ├── server.py           # HTTP server (stdlib) + SSE
│       └── static/index.html   # Frontend
│
├── pipelines/                  # Pipeline definitions (4 templates)
│   ├── retail-replenish.yaml
│   ├── manufacturing-mrp.yaml
│   ├── markdown-clearance.yaml
│   └── promo-planning.yaml
│
├── datasets/                   # Sample data
│   └── retail_grocery/         # Retail grocery dataset
│       ├── sample_demand.csv
│       ├── sku_master.csv
│       └── inventory_snapshot.csv
│
└── tests/                      # Test suite (231 tests)
    ├── test_core.py            # Algorithm unit tests
    ├── test_protocol.py        # Schema & validator tests
    ├── test_phase2.py          # Phase 2 integration (demand/inventory expansion)
    ├── test_phase3.py          # Phase 3 integration (pricing/fulfillment/what-if)
    └── test_agent_tools.py     # 🆕 Agent Toolkit tests (29 tests)
```

## 🛠️ Algorithm Design Principles

| 决策 | 选择 | 不选择 | 理由 |
|------|------|--------|------|
| 时序预测 | MA / EMA / HW / STL / Croston | 深度学习 (LSTM/Transformer) | 轻量、可解释、无 GPU 依赖 |
| 库存优化 | EOQ / ROP / (s,S) / Monte Carlo | 复杂随机规划求解器 | 经典实用，参数直觉清晰 |
| 分类 | ABC-XYZ / 生命周期 | 深度聚类 | 业务可解释性强 |
| 定价 | 弹性回归 / 经济学模型 | 深度强化学习 | 可解释、数据需求小 |
| 履约 | TSP / 波次规划 / 能力检查 | 商业求解器 | 开源覆盖 80% 场景 |
| 后端服务 | Python stdlib http.server | FastAPI/uvicorn | 零依赖，降低部署复杂度 |
| Agent 工具 | ToolSpec/Handler/Router (ml-intern 模式) | 自定义协议 | 标准化、即插即用 |

**LLM 的角色定位——不替代算法，而是增强编排：** 数据翻译官、流程编排者、结果解读者、知识补充者。

## 📈 Roadmap

### Phase 1 ✅ Foundation

- [x] Project skeleton + pyproject.toml
- [x] Unified Data Protocol (Pydantic schemas)
- [x] Core algorithm engine (7 modules)
- [x] 7 core Skills (profiler, forecast, anomaly, classify, safety-stock, reorder, report)
- [x] CLI framework (Click-based)
- [x] Pipeline engine + YAML orchestration
- [x] Sample dataset (retail grocery)
- [x] Memory system (Working / Domain / Meta)
- [x] Dashboard (SSE + HTTP API)
- [x] HITL engine (3-level approval)

### Phase 2 ✅ Intelligence

- [x] Complete demand module (decompose, newproduct, intermittent, reconcile)
- [x] Complete inventory module (policy-sim, multi-echelon, newsvendor)
- [x] Learning Loop + Skill Evolution
- [x] MCP Server adapter (Claude Code compatible)
- [x] Enhanced Dashboard (Memory Insights, Decision History)

### Phase 3 ✅ Ecosystem

- [x] Pricing module (markdown, lifecycle, elasticity, bundling)
- [x] Fulfillment module (allocation, routing, wave, capacity)
- [x] What-If multi-scenario simulation
- [x] LangChain Adapter
- [x] 4 Pipeline templates (MRP, clearance, new-store, promo)

### Phase 4 ✅ Agent Toolkit 🆕

- [x] ToolSpec/ToolRouter architecture (ml-intern pattern)
- [x] 20+ async tool handlers across 5 domains
- [x] OpenAI function-calling format export
- [x] SKILL.md — agent-facing skill description
- [x] Parallel tool execution support
- [x] **29 agent toolkit tests + 202 existing = 231 total passing** ✅

### Phase 5 📋 Next

- [ ] Real-world dataset integration
- [ ] Benchmark suite against industry standards
- [ ] Multi-agent orchestration (research sub-agent pattern)
- [ ] Enterprise features (SSO, audit log)

## 🧪 Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Result: 231 passed ✅
```

Test coverage:

| Test File | Scope | Count |
|-----------|-------|-------|
| `test_core.py` | Algorithm engine (timeseries, inventory, optimization, statistics, classification) | ~25 |
| `test_protocol.py` | Data protocol schemas, validators, CSV adapters | ~15 |
| `test_phase2.py` | Phase 2 skills (demand expansion, inventory expansion, learning, MCP) | ~40 |
| `test_phase3.py` | Phase 3 skills (pricing, fulfillment, what-if, LangChain adapter) | ~30 |
| `test_agent_tools.py` | 🆕 Agent Toolkit (registry, handlers, OpenAI format, workflows) | 29 |
| **Total** | | **231** |

## 🤖 Integration Examples

### With Any LLM (OpenAI format)

```python
from supplymind.agent import get_tool_router

router = get_tool_router()
tools = router.get_tool_specs_for_llm()  # → pass to openai.ChatCompletion.create(tools=tools)
```

### With LangChain

```python
from supplymind.adapters.langchain_tool import get_all_tools
tools = get_all_tools()
agent = create_react_agent(llm, tools, prompt)
```

### With Claude Code / CatPaw (Native Skill)

**Zero setup required.** SupplyMind includes a native Claude Code Skill at `.claude/skills/supplymind/SKILL.md`. When working in this project:

```bash
# Claude Code auto-discovers the skill and can execute any tool:
# User: "Forecast demand for the next 14 days"
# Claude: → reads SKILL.md → runs: python -m supplymind demand-forecast --input data.csv --horizon 14

# Or use the quick runner:
./.claude/skills/supplymind/scripts/sm.sh demand-forecast --input data.csv --horizon 14
```

The skill declares `allowed-tools: [Bash, Read, Write]` so Claude can execute CLI commands, read results, and write output files.

### With MCP Server

```python
from supplymind.mcp.server import MCPServer
server = MCPServer()
server.start_stdio_server()   # or start_mcp_server(transport="http")
# Connect from any MCP client: Claude Desktop, Cursor, VS Code, etc.
```

### Comparison: All Integration Methods

| Method | Protocol | Setup Effort | Best For |
|--------|----------|-------------|----------|
| **Claude Code Skill** | Prompt Injection + Bash CLI | ⭐ Zero (auto-discover) | Claude Code, CatPaw users |
| **Python API (ToolRouter)** | Async function calls | ⭐ Import & call | Custom agents, OpenAI format |
| **LangChain Adapter** | BaseTool wrapper | ⭐ Import & call | LangChain/LangGraph apps |
| **MCP Server** | JSON-RPC (stdio/HTTP) | ⭐⭐ Start server | Any MCP-compatible client |
| **CLI** | Shell command | ⭐ Zero | Scripts, CI/CD, manual use |

## 🤝 Contributing

欢迎贡献！SupplyMind 允许多层次参与：

| 类型 | 说明 |
|------|------|
| 🧮 新算法 | 在 `core/` 中添加新的算法实现 |
| 🧩 新 Skill | 创建新的业务 Skill（遵循统一规范） |
| 🔗 新 Handler | 在 `agent/skill_handlers/` 中添加新工具桥接 |
| 📊 数据集 | 贡献行业数据集到 `datasets/` |
| 🐛 Bug 修复 | 报告和修复问题 |

每个 Skill 的目录结构：
```
skill-name/
├── main.py         # Core logic class with .run() method
├── cli.py          # Click CLI entry
├── schema.py       # Pydantic Input/Output models
└── tests/          # Unit tests
```

每个 Agent Tool Handler 的模式：
```python
# supplymind/agent/skill_handlers/{domain}.py

XXX_TOOL_SPEC = {          # ← LLM sees this
    "name": "tool_name",
    "description": "When and how to use...",
    "parameters": {...},    # JSON Schema
}

async def xxx_handler(arguments: dict) -> tuple[str, bool]:
    """Bridge: args → Pydantic → skill.run() → markdown"""
    input_data = XxxInput(**arguments)
    result = await _run_sync(skill.run, input_data)
    return _format_result(result), True
```

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE)

## 🙏 Acknowledgments

- **HuggingFace ml-intern** — ToolSpec/ToolRouter architecture pattern that inspired the Agent Toolkit layer
- Algorithm references: Hyndman & Athanasopoulos "Forecasting", Silver et al. "Inventory Management"
- Design inspiration: LangChain Tools, OpenAI Plugins, MCP Protocol, Anthropic Skills
- Built for the open-source supply chain community

---

<p align="center">
  <sub>SupplyMind — 不做平台，做供应链的瑞士军刀。</sub>
</p>

---

<a id="english">English</a> | <a id="中文">中文</a>
