<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License" />
  <img src="https://img.shields.io/badge/Tests-60%20passing-brightgreen.svg" alt="Tests" />
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

## 📐 Architecture

SupplyMind 采用三层架构设计：

```
╔═══════════════════════════════════════════════════════════════════╗
║                   Layer 3: Intelligence                         ║
║   Learning Loop │ Memory System │ User Modeling │ Evolution     ║
╠═══════════════════════════════════════════════════════════════════╣
║                   Layer 2: Interaction                           ║
║   HITL Engine (3-level) │ Live Dashboard │ Pipeline Builder      ║
╠═══════════════════════════════════════════════════════════════════╣
║                   Layer 1: Capabilities                          ║
║   Demand Skills │ Inventory Skills │ Common Utils              ║
║   ─────────────────────────────────────────────────────────────  ║
║        Algorithm Engine (core/)  +  Data Protocol (protocol/)    ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Layer 1: Capabilities — Skills & Algorithms

#### Core Algorithm Engine (`supplymind/core/`)

| 模块 | 算法 |
|------|------|
| `timeseries.py` | Moving Average, EMA, Holt-Winters, STL Decomposition, Croston's Method, Auto Forecast |
| `inventory_models.py` | EOQ, ROP, Safety Stock (service level / stochastic), Newsvendor, (s,S) Policy Simulation |
| `optimization.py` | Linear Programming allocation, TSP (Nearest Neighbor + 2-opt) |
| `statistics.py` | Z-score/IQR Outlier Detection, Bootstrap CI, Coefficient of Variation |
| `classification.py` | ABC Analysis (Pareto), XYZ Classification, ABC-XYZ Matrix |

#### Skills (`supplymind/skills/`)

| Skill | 功能 | 输入 | 输出 |
|-------|------|------|------|
| `data-profiler` | 数据质量分析 & 统计摘要 | CSV/JSON | 数据画像报告 |
| `demand-forecast` | 时序需求预测 | 历史销量 + horizon | 逐日预测 + 置信区间 |
| `demand-anomaly` | 异常检测与清洗 | 销售数据 | 清洗后数据 + 异常标记 |
| `inventory-classify` | ABC-XYZ 分类 | SKU 列表 + 销量 | 3×3 矩阵分类 |
| `inventory-safety-stock` | 安全库存计算 | 需求分布 + 提前期 | 各 SKU 安全库存建议 |
| `inventory-reorder` | 补货建议生成 | 预测 + 库存 + SS | 补货清单 + 紧急度排序 |
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
├── pyproject.toml                  # Package config
├── LICENSE                        # Apache 2.0
├── README.md                      # This file
│
├── supplymind/                    # Main package
│   ├── __init__.py               # Version export
│   ├── __main__.py               # python -m supplymind entry
│   ├── cli.py                    # Click CLI (8 subcommands)
│   │
│   ├── core/                     # Algorithm engine (pure Python)
│   │   ├── timeseries.py         # MA, EMA, HW, STL, Croston
│   │   ├── inventory_models.py   # EOQ, ROP, SS, Newsvendor, (s,S)
│   │   ├── optimization.py       # LP, TSP, 2-opt
│   │   ├── statistics.py         # Outlier detection, bootstrap, CV
│   │   └── classification.py     # ABC, XYZ, ABC-XYZ matrix
│   │
│   ├── protocol/                # Data protocol
│   │   ├── schema.py            # Pydantic models (SKUMaster, DemandRecord, ...)
│   │   ├── adapter.py           # CSV/JSON → UDP loader
│   │   └── validators.py        # Data quality checks
│   │
│   ├── skills/                  # Business skills
│   │   ├── common/
│   │   │   ├── data_profiler/   # Data quality profiling
│   │   │   └── report_generator/ # Markdown/HTML reports
│   │   ├── demand/
│   │   │   ├── forecast/        # Demand forecasting
│   │   │   └── anomaly/          # Anomaly detection & cleaning
│   │   └── inventory/
│   │       ├── classify/         # ABC-XYZ classification
│   │       ├── safety_stock/     # Safety stock calculation
│   │       └── reorder/          # Reorder suggestions
│   │
│   ├── pipelines/               # Pipeline engine
│   │   └── engine.py            # YAML executor with HITL integration
│   │
│   ├── memory/                  # Memory system
│   │   ├── working.py           # Session-level memory
│   │   ├── domain.py            # Project-level domain memory
│   │   ├── meta.py              # Agent-level meta memory
│   │   └── store.py             # JSON file store backend
│   │
│   ├── hitl/                    # Human-in-the-Loop
│   │   ├── engine.py            # 3-level approval system
│   │   ├── confidence.py        # Confidence scoring
│   │   └── feedback.py           # Feedback collector
│   │
│   └── dashboard/              # Web UI
│       ├── server.py            # HTTP server (stdlib) + SSE
│       └── static/index.html    # Frontend
│
├── pipelines/                    # Pipeline definitions
│   └── retail-replenish.yaml    # Retail replenishment pipeline
│
├── datasets/                    # Sample data
│   └── retail_grocery/          # Retail grocery dataset
│       ├── sample_demand.csv
│       ├── sku_master.csv
│       └── inventory_snapshot.csv
│
└── tests/                       # Test suite (60 tests)
    ├── test_core.py              # Algorithm unit tests
    ├── test_protocol.py          # Schema & validator tests
    └── test_skills.py            # Skill integration tests
```

## 🛠️ Algorithm Design Principles

| 决策 | 选择 | 不选择 | 理由 |
|------|------|--------|------|
| 时序预测 | MA / EMA / HW / STL / Croston | 深度学习 (LSTM/Transformer) | 轻量、可解释、无 GPU 依赖 |
| 库存优化 | EOQ / ROP / (s,S) / Monte Carlo | 复杂随机规划求解器 | 经典实用，参数直觉清晰 |
| 分类 | ABC-XYZ / 生命周期 | 深度聚类 | 业务可解释性强 |
| 线性优化 | scipy.optimize.linprog | 商业求解器 (Gurobi/COPT) | 开源，覆盖 80% 场景 |
| 后端服务 | Python stdlib http.server | FastAPI/uvicorn | 零依赖，降低部署复杂度 |

**LLM 的角色定位——不替代算法，而是增强编排：** 数据翻译官、流程编排者、结果解读者、知识补充者。

## 📈 Roadmap

### Phase 1 ✅ Foundation (Current)

- [x] Project skeleton + pyproject.toml
- [x] Unified Data Protocol (Pydantic schemas)
- [x] Core algorithm engine (5 modules)
- [x] 7 core Skills (profiler, forecast, anomaly, classify, safety-stock, reorder, report)
- [x] CLI framework (Click-based, 8 commands)
- [x] Pipeline engine + YAML orchestration
- [x] Sample dataset (retail grocery)
- [x] Memory system (Working / Domain / Meta)
- [x] Dashboard (SSE + HTTP API)
- [x] HITL engine (3-level approval)
- [x] **60 tests all passing**

### Phase 2 🔄 Intelligence (Next)

- Complete demand module (decompose, newproduct, intermittent, reconcile)
- Complete inventory module (policy-sim, multi-echelon, newsvendor)
- Learning Loop + Skill Evolution
- MCP Server adapter (Claude Code compatible)
- Enhanced Dashboard (Memory Insights, Decision History)

### Phase 3 📋 Ecosystem

- Pricing module (markdown, lifecycle, elasticity, bundling)
- Fulfillment module (allocation, routing, wave, capacity)
- What-If multi-scenario simulation
- Framework Adapters (OpenClaw, Hermes, LangChain)
- LLM-powered data adapter

### Phase 4 🔮 Scale

- Multi-tenant support
- Skill Marketplace
- Benchmark suite
- Enterprise features (SSO, audit log)

## 🧪 Tests

```bash
# Run all tests
pip install -e .
pytest tests/ -v

# Result: 60 passed ✅
```

Test coverage:
- **test_core.py** — Algorithm engine (timeseries, inventory, optimization, statistics, classification)
- **test_protocol.py** — Data protocol schemas, validators, CSV adapters
- **test_skills.py** — All 7 Skills end-to-end integration

## 🤝 Contributing

欢迎贡献！SupplyMind 允许多层次参与：

| 类型 | 说明 |
|------|------|
| 🧮 新算法 | 在 `core/` 中添加新的算法实现 |
| 🧩 新 Skill | 创建新的业务 Skill（遵循统一规范） |
| 🔗 新 Adapter | 适配新的 Agent 框架 |
| 📊 数据集 | 贡献行业数据集到 `datasets/` |
| 🐛 Bug 修复 | 报告和修复问题 |

每个 Skill 的目录结构：
```
skill-name/
├── SKILL.md        # Skill specification
├── main.py         # Core logic class
├── cli.py          # Click CLI entry
├── schema.py       # Pydantic Input/Output models
└── tests/          # Unit tests
```

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE)

## 🙏 Acknowledgments

- Algorithm references: Hyndman & Athanasopoulos "Forecasting", Silver et al. "Inventory Management"
- Design inspiration: LangChain Tools, OpenAI Plugins, MCP Protocol
- Built for the open-source supply chain community

---

<p align="center">
  <sub>SupplyMind — 不做平台，做供应链的瑞士军刀。</sub>
</p>

---

<a id="english">English</a> | <a id="中文">中文</a>
