# SupplyMind 详细开发计划

> 基于 README.md 中定义的架构、Roadmap 和项目规范，制定的可执行分阶段开发计划。
> 当前状态：**仅存在 README.md，需从零构建整个项目**

---

## 总体开发策略

### 核心原则
1. **最小可用优先**：每个 Phase 结束都可交付可运行版本
2. **Skill 独立可测**：每个 Skill 可单独 CLI 调用，不依赖 Pipeline
3. **零框架锁定**：core/ 纯 Python + numpy/pandas/scipy，无 Agent 框架依赖
4. **渐进增强**：先 CLI → 再 Dashboard → 最后 Framework Adapter

### 技术栈确认
| 层面 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 类型注解、dataclass、match 语句 |
| 核心计算 | numpy, pandas, scipy | 数值计算、数据框、优化求解 |
| CLI | click | 命令行框架 |
| 数据校验 | pydantic v2 | Schema 定义与校验 |
| 配置 | pyyaml | YAML 解析（Pipeline 定义等） |
| 前端 | Alpine.js + Tailwind CSS (CDN/本地) | 零构建 |
| 后端服务 | Python stdlib http.server | 零外部依赖 |
| 实时通信 | SSE (Server-Sent Events) | 单向推送 |
| 可选依赖 | prophet, matplotlib | 按需安装 |

---

## Phase 1: Foundation（基础框架）— 第 1-2 周

### 目标
搭建项目骨架，实现核心算法引擎和数据协议，跑通最小 Demo（单个 Skill CLI 调用成功）

### Step 1.1: 项目初始化结构搭建 — 0.5 天

**任务清单：**
- [ ] 创建 `pyproject.toml`（包名 `supplymind`，依赖声明）
- [ ] 创建完整目录结构（所有 __init__.py）
- [ ] 创建 `.gitignore`（Python 标准 + IDE + __pycache__）
- [ ] 创建 `LICENSE`（Apache 2.0）
- [ ] 创建基础 `tests/conftest.py`（pytest fixtures）

**目录骨架：**
```
supplymind/
├── pyproject.toml
├── README.md
├── LICENSE
├── supplymind/                  # 主包
│   ├── __init__.py              # 版本号导出
│   ├── core/                    # 算法引擎
│   │   ├── __init__.py
│   │   ├── timeseries.py
│   │   ├── inventory_models.py
│   │   ├── optimization.py
│   │   ├── statistics.py
│   │   └── classification.py
│   ├── protocol/                # 数据协议
│   │   ├── __init__.py
│   │   ├── schema.py            # Pydantic models（替代 schema.yaml 的 Python 版）
│   │   ├── adapter.py
│   │   └── validators.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── working.py
│   │   ├── domain.py
│   │   ├── meta.py
│   │   └── store.py
│   ├── hitl/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── confidence.py
│   │   └── feedback.py
│   ├── learning/
│   │   ├── __init__.py
│   │   └── loop.py
│   └── skills/
│       ├── __init__.py
│       ├── common/
│       │   ├── data_profiler/
│       │   ├── data_adapter/
│       │   ├── report_generator/
│       │   └── what_if/
│       ├── demand/
│       │   ├── forecast/
│       │   ├── anomaly/
│       │   ├── decompose/
│       │   ├── newproduct/
│       │   ├── intermittent/
│       │   └── reconcile/
│       ├── inventory/
│       │   ├── classify/
│       │   ├── safety_stock/
│       │   ├── reorder/
│       │   ├── policy_sim/
│       │   ├── multi_echelon/
│       │   └── newsvendor/
│       ├── pricing/
│       └── fulfillment/
├── pipelines/
│   ├── engine.py
│   └── retail-replenish.yaml
├── dashboard/
│   ├── server.py
│   ├── index.html
│   └── static/
├── datasets/
│   └── retail_grocery/
├── adapters/
├── docs/
└── tests/
```

### Step 1.2: Unified Data Protocol（UDP）— 1 天

**文件**: `protocol/schema.py`

**核心 Pydantic Model 设计：**

```python
# 四大核心实体
class SKUMaster(BaseModel):
    sku_id: str
    name: str
    category: list[str]
    unit: str = "件"
    unit_cost: float = 0.0
    unit_price: float = 0.0
    shelf_life_days: int | None = None
    lead_time_days: float = 7.0
    moq: float | None = None
    tags: list[str] = []

class DemandRecord(BaseModel):
    sku_id: str
    location_id: str
    date: date
    quantity: float
    revenue: float | None = None
    is_promo: bool | None = None
    stockout_flag: bool | None = None

class InventorySnapshot(BaseModel):
    sku_id: str
    location_id: str
    date: date
    on_hand: float
    in_transit: float | None = None
    allocated: float | None = None
    available: float | None = None  # auto-derive if None

class LocationMaster(BaseModel):
    location_id: str
    name: str
    type: Literal["store", "dc", "factory"]
    parent_id: str | None = None
    capacity: float | None = None
    lat: float | None = None
    lon: float | None = None
```

**额外交付：**
- [ ] `protocol/validators.py` — 数据质量校验规则（必填字段、数值范围、日期连续性检查）
- [ ] `protocol/adapter.py` — CSV/JSON → UDP Model 的加载工具函数
- [ ] 编写 Schema 相关单元测试

### Step 1.3: Core Algorithm Engine — 3 天

这是整个项目的基石，所有 Skill 都依赖 core/。

#### 1.3.1: `core/timeseries.py` — 时间序列算法库（1.5 天）

**必须实现的算法：**

| 函数 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `moving_average(values, window)` | 简单移动平均 | list[float], int → list[float] | 平滑后序列 |
| `exponential_moving_average(values, alpha)` | 指数移动平均 | list[float], float → list[float] | 平滑后序列 |
| `holt_winters(values, seasonality_periods, horizon, ...)` | Holt-Winters 三参数平滑 | list[float], int, int → ForecastResult | 预测值 + 置信区间 |
| `stl_decompose(values, period)` | STL 分解 | list[float], int → DecompositionResult | trend + seasonal + residual |
| `croston_forecast(values, horizon)` | Croston 间歇性预测 | list[int], int → ForecastResult | 间歇需求预测 |

**ForecastResult 数据结构：**
```python
@dataclass
class ForecastResult:
    predicted: list[float]        # 点预测
    lower: list[float]             # 置信区间下界
    upper: list[float]             # 置信区间上界
    method_used: str               # 使用的方法
    metrics: dict                  # {mape, mae, rmse} (in-sample fit)
```

**Prophet 可选降级策略：**
```python
def forecast_with_fallback(values, horizon, method="auto"):
    """自动选择方法，prophet 可选"""
    if method == "auto":
        method = _auto_select_method(values)
    if method == "prophet":
        try:
            import prophet
            return _prophet_forecast(values, horizon)
        except ImportError:
            logger.info("Prophet not installed, falling back to Holt-Winters")
            return holt_winters(values, horizon)
    # ... 其他方法
```

#### 1.3.2: `core/inventory_models.py` — 库存模型（1 天）

| 函数 | 功能 | 公式/说明 |
|------|------|-----------|
| `eoq(demand_rate, order_cost, holding_cost)` | 经济订货批量 | √(2DS/H) |
| `rop(demand_leadtime, safety_stock)` | 补货点 | d×L + SS |
| `ss_service_level(std_demand, std_lt, service_level, z_table)` | 安全库存（服务水平法） | z × σ_dL |
| `ss_stochastic(demand_dist, lead_time_dist, service_level)` | 安全库存（双随机） | Monte Carlo 近似 |
| `newsvendor(cu, co, price_dist)` | 报童模型最优订货 | F(q*) = cu/(cu+co) |
| `(s_S_policy)(s, S, inventory, demand)` | (s,S) 策略仿真 | 当库存 ≤ s 时补到 S |

#### 1.3.3: `core/optimimization.py` + `core/statistics.py` + `core/classification.py`（0.5 天）

**optimization.py:**
- `allocate_linear_program(supplies, demands, costs)` — scipy.optimize.linprog 包装
- `nearest_neighbor_tsp(locations)` — TSP 最近邻启发式
- `opt_2_opt(route, distance_matrix)` — 2-opt 改进

**statistics.py:**
- `detect_outliers_zscore(values, threshold=3)` — Z-score 异常检测
- `detect_outliers_iqr(values, k=1.5)` — IQR 异常检测
- `bootstrap_confidence_interval(values, n_samples=1000)` — Bootstrap 置信区间
- `coefficient_of_variation(values)` — 变异系数 CV

**classification.py:**
- `abc_analysis(items, value_key)` — ABC 分类（帕累托）
- `xyz_classification(items, cv_thresholds)` — XYZ 分类（变异系数）
- `abc_xyz_matrix(items)` — 组合 3×3 矩阵

### Step 1.4: 第一个 Skill — data-profiler — 1 天

作为最基础的 Skill，data-profiler 用于理解输入数据。

**目录结构：**
```
skills/common/data_profiler/
├── SKILL.md           # Skill 规范文档
├── main.py            # 核心逻辑类 DataProfiler
├── cli.py             # click CLI 入口
├── schema.py          # Input/Output Pydantic models
└── tests/
    └── test_profiler.py
```

**功能要点：**
- 加载 CSV/JSON 数据并映射到 UDP Schema
- 计算统计摘要（SKU 数量、时间范围、缺失率、均值/标准差/分位数）
- 数据质量评分（0-100 分）
- 检测潜在问题（缺失值、异常值、重复记录、时间断点）
- 输出标准化报告（dict / JSON）

**CLI 接口：**
```bash
supplymind data-profiler --input data.csv --output profile.json
```

### Step 1.5: 核心 Skills 实现（第一批 6 个）— 5 天

按优先级排序：

#### 1.5.1: demand-forecast（1.5 天）⭐ 最核心
- 调用 `core/timeseries.py` 中的算法
- 实现 `method="auto"` 自动选择逻辑（根据数据特征选择最佳方法）
- 输出 ForecastOutput（含 confidence_score 用于 HITL 判断）
- CLI: `supplymind demand-forecast --input data.json --horizon 14 --method auto`
- 示例数据集验证

#### 1.5.2: demand-anomaly（0.5 天）
- 调用 `core/statistics.py` 异常检测
- 支持 Z-score / IQR / Isolation Forest（sklearn 可选）
- 输出异常点列表 + 清洗后数据
- 清洗前后对比报告

#### 1.5.3: inventory-classify（0.5 天）
- 调用 `core/classification.py` ABC-XYZ
- 输出分类结果 + 可视化数据（供 Dashboard 使用）
- 支持自定义阈值

#### 1.5.4: inventory-safety-stock（0.5 天）
- 调用 `core/inventory_models.py` 安全库存算法
- 支持服务水平法和双随机法
- 输入：需求分布参数、提前期分布参数、目标服务水平
- 输出：各 SKU 安全库存建议

#### 1.5.5: inventory-reorder（1 天）
- 调用 EOQ / ROP / (s,S) 模型
- 结合预测结果和安全库存生成补货建议
- 输出：补货 SKU 列表 + 建议数量 + 预估成本 + 紧急度排序
- 这是 HITL Level 3 (Collaborate) 的主要触发点

#### 1.5.6: report-generator（0.5 天）
- 将任意 Skill 输出渲染为 Markdown / HTML 报告
- 模板化输出
- 支持嵌入图表数据（Chart.js JSON 格式）

### Step 1.6: CLI 框架 + Python API — 1 天

**统一 CLI 入口 (`supplymind/__main__.py`)：**
```bash
# 安装后使用
pip install -e .
supplymind --help
# supplymind demand-forecast --input ...
# supplymind inventory-classify --input ...
# supplymind run-pipeline retail-replenish.yaml --data ...
```

**click Group 结构：**
```
supplymind
├── demand
│   ├── forecast
│   ├── anomaly
│   ├── decompose
│   ├── newproduct
│   ├── intermittent
│   └── reconcile
├── inventory
│   ├── classify
│   ├── safety-stock
│   ├── reorder
│   ├── policy-sim
│   ├── multi-echelon
│   └── newsvendor
├── pricing
├── fulfillment
├── common
│   ├── data-profiler
│   ├── data-adapter
│   ├── report-generator
│   └── what-if
└── run-pipeline          # 执行 YAML Pipeline
```

**Python API 规范：**
每个 Skill 暴露统一的 `.run(input_data, **params) -> Output` 接口。

### Step 1.7: Pipeline 引擎 + YAML 编排 — 1.5 天

**文件**: `pipelines/engine.py`

**核心能力：**
- 解析 Pipeline YAML（Pydantic model 校验）
- 按序执行 Steps，支持 `$variable` 引用上游输出
- 错误处理：skip / retry / abort 策略
- HITL 集成点（预留接口，Phase 1 先实现 none/auto 两级）
- 执行日志 + 耗时统计
- SSE 事件发射（为 Dashboard 准备）

**Pipeline 执行状态机：**
```
pending → running → completed
                → failed (retry → running | abort)
                → waiting_hitl → approved | rejected | adjusted
```

**第一个预置 Pipeline：retail-replenish.yaml**
```
data-profiler → demand-anomaly → demand-forecast → 
inventory-classify → inventory-safety-stock → 
inventory-reorder → report-generator
```
端到端跑通，7/7 步全部通过。

### Step 1.8: 示例数据集 — 1 天

**数据集 1: datasets/retail_grocery/（生鲜零售）**
- `sample_demand.csv`: 91天 × 2门店 × 5 SKU = 910 条
- `sku_master.csv`: 5 个 SKU 主数据（含品类、成本、提前期）
- `inventory_snapshot.csv`: 最新库存快照
- 场景特点：日销售、强季节性、促销影响、部分缺货记录

**数据集 2: datasets/retail_fmcg/（快消品）**
- 180天 × 5门店 × 15 SKU
- 周粒度为主，含月度汇总
- 多级分类（部门→类别→子类别）

**数据集 3: datasets/manufacturing_auto/（汽车零部件制造）**
- BOM 结构关联
- 多级仓库（工厂→RDC→客户）
- 月度物料需求

### Step 1.9: Memory System（基础版）— 1 天

**Working Memory (`memory/working.py`):**
- 内存字典，存储当前会话上下文
- Pipeline 中间结果缓存
- 会话结束即销毁

**Domain Memory (`memory/domain.py`):**
- JSON 文件持久化（`.supplymind/domain_memory.json`）
- 四类记忆的 CRUD 接口：
  - 数据画像记忆
  - 参数偏好记忆
  - 模型表现记忆
  - 异常模式记忆
- 按 project_id 隔离

**Store (`memory/store.py`):**
- 抽象存储后端（默认 JSONFileStore）
- 预留 SQLiteStore 接口

### Step 1.10: Dashboard（基础版）— 2 天

**后端 `dashboard/server.py`:**
- 基于 `http.server.HTTPServer` + `ThreadingMixIn`
- SSE 端点：`/events` — 推送 Pipeline 执行状态
- REST API:
  - `GET /api/status` — Agent 状态
  - `GET /api/pipeline` — Pipeline 执行详情
  - `POST /api/pipeline/run` — 触发执行
  - `GET /api/kpi` — KPI 数据
  - `GET /api/forecast` — 预测结果
  - `GET /api/abc-xyz` — 分类结果
  - `GET /api/reorder` — 补货建议
  - `GET /api/inventory` — 库存对比
  - `POST /api/hitl/:id/approve` — HITL 审批
  - `POST /api/hitl/:id/reject` — HITL 驳回
- 启动时自动执行示例 Pipeline

**前端 `dashboard/index.html`:**
- 单 HTML 文件，Alpine.js + Tailwind CSS（CDN 引入）
- 页面布局：
  - 顶部导航栏（Agent 状态指示器）
  - KPI 卡片行（4 个核心指标）
  - Pipeline 执行流（7 步可视化，实时状态 + 耗时）
  - Tab 切换内容区：
    - Tab 1: 需求预测表（MAPE 染色，点击展开逐日明细）
    - Tab 2: ABC-XYZ 矩阵（3×3 热力图 + 明细表）
    - Tab 3: 补货建议表（紧急度排序 + 成本汇总）
    - Tab 4: 安全库存 vs 在手库存（条形图）
- 暗色模式切换
- SSE 自动重连
- 一键重新执行按钮

**本地化静态资源 `dashboard/static/`:**
- 下载 alpine.js、tailwind.js、chart.js 到本地
- 生产环境支持完全离线运行

### Step 1.11: HITL 基础引擎 — 1 天

**`hitl/engine.py`:**
- HITL Session 管理（创建、查询、超时）
- 三级审批逻辑：
  - `auto`: 直接通过，记录决策日志
  - `review`: 生成等待事件，支持 accept/adjust/skip
  - `collaborate`: 生成多方案对比，等待人工选择
- 超时自动采纳机制
- escalate_if 条件评估器

**`hitl/confidence.py`:**
- 置信度计算框架
- 基于模型 MAPE、数据完整性、历史准确率的综合评分

**`hitl/channels/api.py`:**
- HTTP API 通道（Dashboard 用）
- POST/GET 审批操作
- SSE 推送等待审批事件

**HITL Dashboard UI:**
- 审批面板组件（在 Dashboard 内嵌）
- 显示待审批项列表
- 详情展示 + 操作按钮（通过/驳回/调整）
- SSE 实时刷新

### Step 1.12: 测试 + 文档 — 1 天

- [ ] core/ 全部算法单元测试（覆盖边界条件）
- [ ] 6 个核心 Skill 的集成测试
- [ ] Pipeline 端到端测试
- [ ] `docs/getting-started.md` 快速开始指南
- [ ] 确保 `python3 dashboard/server.py` 可以一键启动并看到完整 Demo

---

### Phase 1 交付验收标准

- [ ] `pip install -e .` 成功安装
- [ ] `supplymind data-profiler --input datasets/retail_grocery/sample_demand.csv` 正常输出
- [ ] `supplymind demand-forecast --input ... --horizon 14` 输出预测结果和 MAPE
- [ ] `supplymind run-pipeline pipelines/retail-replenish.yaml --data ...` 7 步全通过
- [ ] `python3 dashboard/server.py` 启动后浏览器可见完整 Dashboard
- [ ] Dashboard 显示 KPI、Pipeline 流程、预测表、ABC-XYZ、补货建议、库存对比
- [ ] 平均 MAPE 在示例数据集上 ≤ 15%
- [ ] 所有核心代码有对应单元测试

---

## Phase 2: Intelligence（智能闭环）— 第 3-4 周

### 目标
完善所有 Skills，实现学习闭环和进化能力，MCP Server 适配

### Step 2.1: 完善需求模块（剩余 4 个 Skill）— 3 天

#### 2.1.1: demand-decompose（0.5 天）
- STL 分解封装
- 输出趋势/季节/残差三组分
- 季节性强度指标（用于判断是否需要季节性调整）
- 可视化数据输出

#### 2.1.2: demand-newproduct（1 天）⭐ LLM 增强
- 相似品匹配算法（基于 category 特征向量相似度）
- 品类生长曲线模板（新品导入期典型模式）
- LLM 推理集成（可选）：当有 LLM API 时调用补充领域知识
- 冷启动置信度标记（天然低置信度 → 触发 HITL Review）
- 上市周数追踪

#### 2.1.3: demand-intermittent（0.5 天）
- Croston's method 封装（优化变体：SBA / TSB）
- 自动识别间歇性需求 SKU（CV > 阈值 且 大量零值）
- 与常规预测的自动路由

#### 2.1.4: demand-reconcile（1 天）
- Top-down 按比例拆分
- Bottom-up 汇总 + 差异按比例调整
- Middle-out 混合策略
- 多层级一致性校验（确保各层级加总一致）

### Step 2.2: 完善库存模块（剩余 4 个 Skill）— 3 天

#### 2.2.1: inventory-policy-sim（1 天）
- Monte Carlo 库存策略仿真
- 输入：需求分布、提前期分布、策略参数(s,S)/(s,Q)
- 输出：服务水平、缺货次数、平均库存、周转率
- 多策略对比（并行仿真 N 次）
- 可视化：库存水平随时间变化曲线

#### 2.2.2: inventory-multi-echelon（1 天）
- 简化 METRIC 模型（两级：工厂→RDC 或 RDC→门店）
- 延迟策略（Postponement）建模
- 安全库存搁置（Safety Stock Placement）
- 输出：各级最优安全库存分配

#### 2.2.3: inventory-newsvendor（0.5 天）
- 经典报童模型
- 支持离散/连续需求分布
- 敏感性分析（成本参数变化对最优量的影响）
- 与定价模块联动预备

#### 2.2.4: （inventory-safety-stock 增强）（已在 Phase 1 完成，此处增强双随机法）

### Step 2.3: Learning Loop 学习闭环 — 2.5 天

**`learning/loop.py` — 主控制器：**

```python
class LearningLoop:
    """学习闭环主逻辑"""
    
    def on_feedback(self, decision_id, feedback: Feedback):
        """收到反馈时触发"""
        # 1. 分析反馈类型（隐式/显式）
        # 2. 更新 Domain Memory
        # 3. 更新 Skill Evolution档案
        # 4. 检查是否需要生成新规则
        
    def periodic_backtest(self):
        """定期回测（定时任务或手动触发）"""
        # 1. 取历史预测 vs 实际销量
        # 2. 计算 post-mortem MAPE
        # 3. 更新 method_performance 记录
        # 4. 调整算法偏好权重
```

**`learning/backtest.py` — 回测系统：**
- 滚动窗口回测（rolling-origin evaluation）
- 按品类/按方法分解准确率
- 自动生成回测报告
- 回测结果写入 Domain Memory

**`learning/evolution.py` — Skill 进化：**
- 维护每个 Skill 的 `evolution.yaml`
- 方法性能追踪（avg_mape, best_for, worst_for）
- 用户修正记录（user_corrections）
- 自动规则生成（auto_rules）：
  - 当某品类用方法 A 连续 N 次优于方法 B 时 → 生成偏好规则
  - 当用户连续 M 次手动调整同类型预测 → 生成偏差修正规则

**反馈收集增强 `hitl/feedback.py`:**
- 隐式反馈检测器（采纳/调整幅度/跳过）
- 显式反馈解析器（自然语言修正指令）
- 反馈 → Learning Loop 的桥梁

### Step 2.4: Meta Memory + 完整记忆系统 — 1 天

**`memory/meta.py`:**
- Agent 级别持久化存储
- Skill 使用频率统计
- 用户交互风格画像（详细/简洁偏好）
- 跨项目经验泛化

**记忆桥接 `memory/bridges/generic.py`:**
- 通用框架记忆桥接接口
- 为后续 OpenClaw/Hermes 适配准备

### Step 2.5: HITL Level 3 完善 + Feedback Collector — 1.5 天

**Collaborate 模式完整实现：**
- 多方案生成（基于不同参数组合）
- What-If 对比视图数据
- 方案推荐理由（自然语言生成）
- Dashboard 协作决策 UI

**Feedback Collector Skill:**
- 触发时机：after_human_decision
- 动作：
  - log_decision_and_reasons（记录到 Decision History）
  - update_domain_memory（更新用户偏好）
  - schedule_backtest（14天后回测提醒）

**Decision History Dashboard 组件：**
- 历史决策表格（日期/场景/决策/回测结果）
- 回测结果标注（✅📈⚠️）

### Step 2.6: MCP Server 适配 — 2 天 ⭐ 重要

**`adapters/mcp/mcp_server.py`:**

基于 MCP (Model Context Protocol) 实现 SupplyMind 作为 Tool Server：

```python
# 暴露给 LLM 的 Tools
TOOLS = [
    {
        "name": "demand_forecast",
        "description": "基于历史销售数据生成需求预测",
        "inputSchema": { ... }  # JSON Schema
    },
    {
        "name": "inventory_reorder",
        "description": "生成补货建议",
        "inputSchema": { ... }
    },
    {
        "name": "data_profiler",
        "description": "分析数据质量和统计特征",
        "inputSchema": { ... }
    },
    # ... 更多 tools
]
```

**MCP Server 能力：**
- stdio 传输模式（Claude Code / Claude Desktop 直连）
- 每个 Skill 映射为一个 MCP Tool
- HITL 通过 prompt 返回（请求用户输入）
- Memory 通过 context 注入
- 工具调用结果结构化返回

**测试：**
- Claude Code 中 `supplymind-mcp` 可被识别为 Tool Server
- 可通过对话完成完整的"帮我做需求预测"流程

### Step 2.7: Dashboard 增强 — 1.5 天

**新增面板：**
- Memory Insights 面板（模型表现趋势、已学习经验数、最近学习记录）
- Pending Approvals 面板（待审批项列表 + 超时倒计时）
- Decision History 表格
- Agent Activity Log（实时时间线）

**交互增强：**
- HITL 审批内嵌操作（不再跳转）
- SSE 事件类型扩展（memory_updated, decision_logged, backtest_scheduled）

### Step 2.8: 额外 Pipelines — 1 天

- [ ] `pipelines/markdown-clearance.yaml` — 临期/滞销出清
- [ ] `pipelines/new-store-launch.yaml` — 新店铺货
- [ ] `pipelines/manufacturing-mrp.yaml` — 制造业 MRP
- [ ] `pipelines/promo-planning.yaml` — 促销备货

### Phase 2 交付验收标准

- [ ] 全部 20 个 Skill 可独立 CLI 调用
- [ ] Learning Loop 可自动记录反馈并更新记忆
- [ ] Skill Evolution 档案自动维护
- [ ] MCP Server 可被 Claude Code 识别和使用
- [ ] HITL 三级审批全部可用
- [ ] Dashboard 包含所有面板（含 Memory Insights 和 Decision History）
- [ ] 5 个预置 Pipeline 全部可运行

---

## Phase 3: Ecosystem（生态扩展）— 第 5-6 周

### 目标
定价/履约模块、What-If 模拟、Framework Adapters、Dashboard v2

### Step 3.1: 定价模块（4 个 Skill）— 3 天

#### 3.1.1: pricing-elasticity（0.5 天）
- 对数回归估计价格弹性: ln(Q) = α + β·ln(P)
- 弹性系数 + 置信区间
- 弹性分类（富有弹性/缺乏弹性/单位弹性）

#### 3.1.2: pricing-markdown（1 天）
- 弹性估计 → 最优降价幅度（贪心搜索）
- 出清策略：时效约束下的分阶段降价
- 考虑保质期（shelf_life_days）的紧急程度
- 利润最大化目标函数

#### 3.1.3: pricing-lifecycle（1 天）
- 商品生命周期阶段划分（导入/成长/成熟/衰退）
- 基于销量趋势的阶段判定规则引擎
- 各阶段定价策略建议
- 与 newsvendor 联动（衰退期清仓）

#### 3.1.4: pricing-bundling（0.5 天）
- 捆绑组合建议（互补品检测）
- LLM 推理增强（可选）：品类知识补充
- 促销策略规则约束

### Step 3.2: 履约配送模块（4 个 Skill）— 2.5 天

#### 3.2.1: fulfill-allocation（0.5 天）
- 多仓库存分配（优先级规则 + LP 优化）
- 服务水平约束
- 运输成本考虑

#### 3.2.2: fulfill-routing（1 天）
- TSP 路径规划（最近邻 + 2-opt）
- 支持多点配送、时间窗约束
- 路线可视化数据输出

#### 3.2.3: fulfill-wave（0.5 天）
- 波次计划（时间窗 + 订单截止）
- 贪心分组策略
- 波次效率指标

#### 3.2.4: fulfill-capacity（0.5 天）
- 仓容/产能约束检查
- 瓶颈识别
- 规则引擎（硬约束 + 软约束）

### Step 3.3: What-If 多场景模拟 — 1.5 天

**`skills/common/what_if/main.py`:**

核心能力：
- 参数扫描（Parameter Sweep）：如"提前期 7→21 天，安全库存如何变化"
- 多场景对比：定义多个场景（保守/平衡/激进），并行计算
- 敏感性分析：单因素变动影响
- 与 Dashboard 联动：场景对比图表

**场景定义格式：**
```yaml
scenarios:
  - name: "保守"
    params:
      service_level: 0.90
      forecast_adjustment: 0.8
  - name: "平衡"
    params:
      service_level: 0.95
      forecast_adjustment: 1.0
  - name: "激进"
    params:
      service_level: 0.98
      forecast_adjustment: 1.2
```

### Step 3.4: Framework Adapters — 3 天

#### 3.4.1: OpenClaw Adapter（1 天）
- `adapters/openclaw/SKILL.md` — OpenClaw 格式的 Skill 描述
- CLI wrapper 脚本
- memory → catpaw_mem 桥接
- HITL → daxiang/message 渠道

#### 3.4.2: Hermes Adapter（1 天）
- `adapters/hermes/SKILL.md`
- memory → hermes_mem 桥接
- HITL → telegram/gateway 渠道

#### 3.4.3: LangChain Adapter（社区贡献，1 天）
- `adapters/langchain/tool_wrapper.py`
- LangChain CustomTool 包装
- 适合 LangGraph/LangChain Agent 集成

### Step 3.5: Dashboard v2 — 2 天

**升级内容：**
- WebSocket 双向通信（替代纯 SSE）
- Pipeline Builder 可视化界面（拖拽编排）
- What-If 场景对比图表
- 定价/履约模块的数据面板
- 性能优化（大数据量虚拟滚动）

**注意**：如果不想引入 WebSocket 复杂度，可以保持 SSE + 轮询混合方案。

### Step 3.6: data-adapter Skill（LLM 增强）— 1.5 天

**`skills/common/data_adapter/main.py`:**

- LLM 驱动的 schema 推理（用户上传 CSV → 自动识别列含义）
- mapping.yaml 生成与复用
- 支持多种输入格式：CSV / Excel / JSON / 自然语言描述
- 半交互式确认（不确定的字段询问用户）

### Step 3.7: 行业模板 + 文档 — 1 天

- 4 套行业预置模板配置（零售/制造/生鲜/医药）
- `docs/skill-development-guide.md` — Skill 开发指南
- `docs/hitl-design.md` — HITL 设计文档
- `docs/memory-system.md` — 记忆系统文档
- `docs/api-reference.md` — API 参考
- CONTRIBUTING.md 贡献指南

### Phase 3 交付验收标准

- [ ] 全部 28+ 个 Skill 实现完成
- [ ] What-If 模拟可在 Dashboard 上交互使用
- [ ] OpenClaw / Hermes Adapter 可用
- [ ] MCP Server 稳定
- [ ] data-adapter 可处理常见 CSV/Excel 格式
- [ ] 4 套行业模板就绪

---

## Phase 4: Scale（规模化）— 第 7 周+

### 目标
多租户、社区生态、企业特性

### Step 4.1: 多租户支持
- 项目/租户隔离（目录级隔离 + 配置分离）
- 权限控制基础（RBAC 框架）
- 资源配额管理

### Step 4.2: Skill Marketplace
- Skill 发布规范（打包 + 元数据）
- Skill 安装/卸载机制
- 社区 Skill 共享 registry
- Skill 评分与评论

### Step 4.3: Skill 自动创建
- 操作序列录制
- 模式检测（发现重复操作序列）
- Skill 模板自动填充
- 人类审核流程

### Step 4.4: Benchmark 系统
- 标准评测数据集
- 评测指标体系（MAPE / RMSE / 服务水平 / 库存周转）
- 排行榜系统

### Step 4.5: 企业版特性
- 认证（SSO / LDAP）
- 审计日志
- 数据加密
- 高可用部署方案

---

## 开发优先级矩阵（总体视角）

### P0 — 必须有（Phase 1）
| 模块 | 理由 |
|------|------|
| 项目骨架 + pyproject.toml | 一切的基础 |
| UDP Schema (protocol/) | 数据交换的标准 |
| core/timeseries.py | 预测算法根基 |
| core/inventory_models.py | 库存算法根基 |
| core/statistics.py + classification.py | 异常检测 + 分类 |
| data-profiler Skill | 第一个 Skill，验证规范 |
| demand-forecast Skill | 核心价值 |
| demand-anomaly Skill | 数据质量保障 |
| inventory-classify Skill | ABC-XYZ 是供应链基础 |
| inventory-safety-stock Skill | 补货计算基础 |
| inventory-reorder Skill | 最终业务输出 |
| report-generator Skill | 结果呈现 |
| CLI 框架 (click) | 用户交互入口 |
| Pipeline 引擎 | 流程编排核心 |
| retail-replenish.yaml | 端到端验证 |
| 示例数据集 (retail_grocery) | 测试数据 |
| Memory 基础版 | 智能化基础 |
| Dashboard (server + frontend) | 可视化展示 |
| HITL 基础引擎 | 人机协作 |
| 测试 | 质量保障 |

### P1 — 应该有（Phase 2）
| 模块 | 理由 |
|------|------|
| 剩余需求 Skills (decompose/newproduct/intermittent/reconcile) | 完整需求模块 |
| 剩余库存 Skills (policy-sim/multi-echelon/newsvendor) | 完整库存模块 |
| Learning Loop | 自我改进核心 |
| Skill Evolution | 差异化竞争力 |
| MCP Server | LLM Agent 生态入口 |
| HITL Level 3 (Collaborate) | 完整人机协作 |
| Meta Memory | 跨项目学习 |
| Extra Pipelines (4个) | 覆盖更多场景 |

### P2 — 可以有（Phase 3）
| 模块 | 理由 |
|------|------|
| 定价模块 (4 Skills) | 新业务领域 |
| 履约模块 (4 Skills) | 新业务领域 |
| What-If 模拟 | 决策支持增强 |
| Framework Adapters (OpenClaw/Hermes/LangChain) | 生态扩展 |
| data-adapter (LLM) | 降低使用门槛 |
| Dashboard v2 | 体验升级 |

### P3 — 未来有（Phase 4）
| 模块 | 理由 |
|------|------|
| 多租户 | 企业需求 |
| Skill Marketplace | 社区生态 |
| Benchmark | 行业标准 |
| 企业版 | 商业化 |

---

## 关键技术决策记录（ADR）

### ADR-001: 为什么不用深度学习做时序预测？
**决定**: 使用经典统计模型（MA/EMA/HW/STL/Croston）
**理由**:
- 轻量级，无需 GPU
- 可解释性强（业务人员能理解）
- 小数据量下表现不差于甚至优于深度学习
- Prophet 作为可选升级路径

### ADR-002: 为什么 Dashboard 不用 FastAPI？
**决定**: Python stdlib http.server
**理由**:
- 零外部依赖（Dashboard 本身就是演示/观察工具）
- 降低部署复杂度
- 后续可按需升级到 FastAPI

### ADR-003: 为什么选择 Pydantic 而非 raw dict？
**决定**: 全链路 Pydantic Model
**理由**:
- 自动校验 + 类型提示
- IDE 友好（自动补全）
- 序列化/反序列化一致
- JSON Schema 可自动生成（用于 MCP Tool 定义）

### ADR-004: Skill 进化的边界？
**决定**: 只记录和推荐，不自动修改算法代码
**理由**:
- 安全性：自动改代码风险太高
- 可控性：人类始终在环路中
- 实际方式：维护 evolution.yaml + auto_rules，影响 method 选择逻辑

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 算法准确率不够高 | 用户不信任 | 中 | 先标明置信度 + HITL 审核兜底；持续迭代 |
| LLM API 成本/延迟 | data-adapter 体验差 | 低 | LLM 做可选依赖；mapping 缓存复用 |
| Dashboard stdlib 性能瓶颈 | 并发差 | 低 | 本身是单用户观察工具；后续可升级 |
| 数据格式千差万别 | 适配工作量大 | 高 | UDP Schema + data-adapter + LLM 映射 |
| Skill 间依赖复杂 | Pipeline 调试困难 | 中 | 统一 Input/Output Schema；中间结果可检视 |

---

## 时间线总览（甘特图风格）

```
Week 1                                                                    Week 7+
─────────────────────────────────────────────────────────────────────────────────
P1: Foundation (Day 1-12)
  [====项目初始化====][==UDP==][===Core算法引擎===][=Profiler=][核心Skills...]
                       [==================CLI+API==================][Pipeline..]
                                                              [数据集][Memory][Dash]
                                                                     [HITL][测试]

P2: Intelligence (Day 13-24)
  [==需求模块剩余==][==库存模块剩余==][==LearningLoop==][MCP Server][HITL-L3][Pipe..]

P3: Ecosystem (Day 25-35)
  [==定价模块==][==履约模块==][What-If][FrameworkAdapters][Dashv2][data-adapter][文档]

P4: Scale (Day 36+)
  [多租户][Marketplace][Benchmark][企业版]
```

**预计总工期**: 5-7 周全职开发（Phase 1-3），Phase 4 持续迭代
