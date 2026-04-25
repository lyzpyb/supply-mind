SupplyMind
A self-improving, skill-based supply chain planning agent framework with human-in-the-loop

SupplyMind 是一个开源的供应链计划 Agent 框架。它不是一个重型系统，而是一组可独立使用、可自由组合的 Skill 集合，可以运行在 OpenClaw、Hermes、Claude Code 等任意 Agent 框架上。

它的核心特点：

🧩 Skill-based：每个能力是一个独立 Skill，即插即用
🧠 Self-improving：内置学习闭环，越用越懂你的业务
👤 Human-in-the-loop：三级人机协作，关键决策人类拍板
📊 Observable：轻量 Dashboard 实时观察 Agent 状态
🔌 Framework-agnostic：不绑定任何框架，纯 Python + CLI
Dashboard
零构建、零依赖的 Agent 状态面板。python3 dashboard/server.py 即开即用。

SupplyMind Dashboard

已实现：

📊 概览 KPI 卡片（SKU 数量 / 平均 MAPE / 总安全库存 / 补货成本）
⚡ 7 步 Pipeline 执行流可视化（实时状态 + 耗时）
📈 需求预测汇总表（MAPE 染色 / 趋势指标 / 点击展开逐日明细）
🏷️ ABC-XYZ 分类矩阵（3×3 热力 + 明细表）
🚛 补货建议表（紧急度排序 / 成本汇总）
⚠️ 安全库存 vs 在手库存对比（CSS 条形图 + 补货点标线）
🌙 暗色模式 / SSE 实时推送 / 一键重新执行
📦 前端资源全部本地化（内网可用，无需外网 CDN）
Table of Contents
Quick Start
Why SupplyMind
Architecture
Layer 1: Capabilities — Skills & Algorithms
Layer 2: Interaction — HITL & Dashboard
Layer 3: Intelligence — Memory & Learning
Unified Data Protocol
Framework Adapters
Project Structure
Skill Specification
Pipeline Orchestration
Algorithm Design Principles
Roadmap
Contributing
License
Quick Start
# 克隆
git clone https://github.com/user/supply-mind.git
cd supply-mind

# 安装依赖（仅标准库 + 4 个核心包）
pip install numpy pandas scipy pydantic click pyyaml

# 运行 Dashboard（自动执行示例 Pipeline）
python3 dashboard/server.py
# 浏览器打开 http://localhost:8765

# 或单独运行 Skill
python3 -m skills.demand.forecast.cli --input datasets/retail_grocery/sample_demand.csv --horizon 14

# 或运行完整 Pipeline
python3 pipelines/engine.py pipelines/retail-replenish.yaml --data datasets/retail_grocery/sample_demand.csv
Why SupplyMind
manufacturing-agents	Planiverse (杉数)	SupplyMind
形态	重系统 (LangGraph+MongoDB+Redis+Streamlit)	商业 SaaS 平台	Skill 集合 + 标准数据协议
依赖	LangChain 生态锁定	闭源求解器 (COPT)	零框架依赖，纯 Python/CLI
算法	LLM 角色扮演为主	专业 OR 求解器	轻量统计模型 + LLM 编排
适配性	仅 LangGraph	仅自有平台	OpenClaw / Hermes / Claude Code / MCP
学习能力	无	无	内置学习闭环，持续自我改进
人机交互	无	平台内审批	三级 HITL，嵌入 Pipeline
输入格式	硬编码 JSON	企业级 ETL	通用 Schema + LLM 自适应解析
核心理念：不做平台，做"供应链的瑞士军刀"。每个模块是一个独立 Skill，可单独使用，也可组合成完整流程。Agent 不是替代人类决策，而是成为越来越懂你的供应链搭档。

Architecture
╔══════════════════════════════════════════════════════════════════════════╗
║                         SupplyMind Architecture                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │                   Layer 3: Intelligence                          │    ║
║  │                                                                  │    ║
║  │  ┌────────────┐ ┌───────────────┐ ┌────────────┐ ┌───────────┐ │    ║
║  │  │ Learning   │ │ Memory        │ │ User       │ │ Skill     │ │    ║
║  │  │ Loop       │ │ System        │ │ Modeling   │ │ Evolution │ │    ║
║  │  │            │ │               │ │            │ │           │ │    ║
║  │  │ 从反馈中   │ │ 短期/领域/    │ │ 理解你的   │ │ 自动创建  │ │    ║
║  │  │ 持续改进   │ │ 元记忆        │ │ 业务偏好   │ │ 和改进    │ │    ║
║  │  └────────────┘ └───────────────┘ └────────────┘ └───────────┘ │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │                   Layer 2: Interaction                           │    ║
║  │                                                                  │    ║
║  │  ┌────────────┐ ┌───────────────┐ ┌────────────┐ ┌───────────┐ │    ║
║  │  │ HITL       │ │ Live          │ │ Pipeline   │ │ What-If   │ │    ║
║  │  │ Engine     │ │ Dashboard     │ │ Builder    │ │ Sandbox   │ │    ║
║  │  │            │ │               │ │            │ │           │ │    ║
║  │  │ 审批/修正  │ │ 实时状态      │ │ 可视化     │ │ 场景      │ │    ║
║  │  │ /反馈      │ │ 观察面板      │ │ 流程编排   │ │ 模拟对比  │ │    ║
║  │  └────────────┘ └───────────────┘ └────────────┘ └───────────┘ │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │                   Layer 1: Capabilities                          │    ║
║  │                                                                  │    ║
║  │  ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌───────────┐ ┌──────┐ │    ║
║  │  │ Demand  │ │ Inventory │ │ Pricing │ │ Fulfill-  │ │Common│ │    ║
║  │  │ Skills  │ │ Skills    │ │ Skills  │ │ ment      │ │Utils │ │    ║
║  │  │ (6)     │ │ (6)       │ │ (4)     │ │ Skills(4) │ │ (4)  │ │    ║
║  │  └─────────┘ └───────────┘ └─────────┘ └───────────┘ └──────┘ │    ║
║  │                                                                  │    ║
║  │  ┌──────────────────────────────────────────────────────────┐   │    ║
║  │  │  Algorithm Engine (supplymind-algo) + Data Protocol (UDP) │   │    ║
║  │  └──────────────────────────────────────────────────────────┘   │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════╝
Layer 1: Capabilities
Demand Skills (demand/)
Skill	功能	算法
demand-forecast	基础时序预测	MA, EMA, Holt-Winters, 简单 ARIMA
demand-decompose	需求分解（趋势+季节+残差）	STL 分解
demand-anomaly	历史异常检测与清洗	Z-score, IQR, Isolation Forest
demand-newproduct	新品冷启动预测	相似品类比法 + LLM 推理
demand-intermittent	间歇性需求预测	Croston's method
demand-reconcile	多层级需求一致性校准	Top-down / Bottom-up / Middle-out
Inventory Skills (inventory/)
Skill	功能	算法
inventory-classify	ABC-XYZ 分类	帕累托分析 + 变异系数
inventory-safety-stock	安全库存计算	服务水平法 / 需求-供给双随机
inventory-reorder	补货点与补货量	EOQ / ROP / (s,S) / (s,Q)
inventory-policy-sim	库存策略仿真	蒙特卡洛模拟
inventory-multi-echelon	多级库存优化	简化 METRIC 模型
inventory-newsvendor	报童模型（单周期决策）	经典 Newsvendor
Pricing Skills (pricing/)
Skill	功能	算法
pricing-markdown	Markdown 定价 / 出清策略	弹性估计 + 贪心搜索
pricing-lifecycle	商品生命周期定价	阶段划分 + 规则引擎
pricing-elasticity	价格弹性估计	对数回归
pricing-bundling	捆绑/促销策略建议	LLM 推理 + 约束规则
Fulfillment Skills (fulfillment/)
Skill	功能	算法
fulfill-allocation	多仓库存分配	优先级规则 + 简单 LP
fulfill-routing	配送路径规划	最近邻 / 2-opt 启发式
fulfill-wave	波次计划	时间窗约束 + 贪心
fulfill-capacity	仓容/产能约束检查	规则引擎
Common Utils (common/)
Skill	功能
data-profiler	数据质量检查 & 统计摘要
data-adapter	LLM 驱动的格式自适应转换
report-generator	分析报告生成（Markdown/HTML）
what-if	多场景对比模拟
Layer 2: Interaction
Human-in-the-Loop Engine
供应链决策不是全自动的——错误的补货决策可能导致百万级损失。SupplyMind 设计三级 HITL：

Level 1: Auto（自动执行，事后通知）
触发条件：
  • 置信度 > 90%
  • 金额影响 < 设定阈值
  • 历史同类决策用户从未修正过

示例：常规A类商品日常补货
Agent: "已自动生成补货单，共127个SKU，预计金额¥34.2万 [查看详情]"
Level 2: Review（生成建议，等待确认）
触发条件：
  • 置信度 60%-90%
  • 首次处理的品类/场景
  • 检测到异常数据

示例：新品类首次补货
Agent: "我对这批SKU的预测不太确定：
  • 酸奶-新品X: 建议补300箱（置信区间200-450）
  • 理由：基于相似品Y的历史，但Y是夏季上市
  [✅ 采纳] [✏️ 调整] [❌ 跳过] [💬 讨论]"
Level 3: Collaborate（协作决策）
触发条件：
  • 置信度 < 60%
  • 重大决策（促销备货、清仓定价等）
  • 多目标冲突（成本 vs 服务水平）

示例：大促前备货策略
Agent: "618备货有三个方案，需要你来拍板：
  方案A（保守）: 补¥120万，缺货风险15%
  方案B（平衡）: 补¥180万，缺货风险5%
  方案C（激进）: 补¥250万，缺货风险1%
  [查看对比分析] [进入What-If模拟]
  [选择方案 A/B/C] [自定义方案]"
HITL in Pipeline
# pipelines/retail-replenish.yaml
steps:
  - skill: data-profiler
    output: $profiled
    hitl: none                      # 纯数据处理，无需审批

  - skill: demand-anomaly
    output: $cleaned
    hitl:
      level: review                 # 异常清洗结果需人工确认
      show: "检测到 {count} 个异常点，清洗前后对比"
      actions: [accept, adjust, skip]
      timeout: 30m                  # 30分钟无响应自动采纳

  - skill: demand-forecast
    output: $forecast
    hitl:
      level: auto                   # 常规预测自动通过
      escalate_if:                  # 满足条件时升级审批
        - "mape > 25%"
        - "new_sku_count > 10"
        - "promo_detected"

  - skill: inventory-reorder
    output: $reorder
    hitl:
      level: collaborate            # 补货决策必须人工参与
      present: what-if              # 自动打开 What-If 对比
      require_approval: true

  - skill: feedback-collector
    trigger: after_human_decision
    actions:
      - log_decision_and_reasons
      - update_domain_memory
      - schedule_backtest           # 14天后自动回测
Live Dashboard
一个轻量的 Agent 状态观察窗口，不是重前端系统。

┌──────────────────────────────────────────────────────────────────┐
│  SupplyMind Dashboard                           🟢 Agent Online  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Agent Activity ──────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  ⏱ Current Task: 华北区周补货建议                          │  │
│  │  📊 Progress: ████████░░ 80% (inventory-reorder running)  │  │
│  │                                                            │  │
│  │  Pipeline: data-profiler ✅ → demand-forecast ✅ →         │  │
│  │            inventory-reorder 🔄 → [等待审批] ⏸             │  │
│  │                                                            │  │
│  │  💬 Agent Log:                                             │  │
│  │  14:32  加载数据 1247 SKU, 3 仓库                          │  │
│  │  14:33  异常清洗: 移除3个离群点                             │  │
│  │  14:34  预测完成, 整体MAPE 11.2%                           │  │
│  │  14:35  ⚠️ 23个SKU需要人工审核                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Pending Approvals ───────────┐  ┌─ Memory Insights ──────┐  │
│  │                               │  │                        │  │
│  │  🔴 补货方案待确认 (23 SKU)    │  │  📊 模型表现趋势        │  │
│  │     等待: 12分钟              │  │  HW: MAPE 11.2% ↓      │  │
│  │     [去审批]                  │  │  MA: MAPE 14.8% →      │  │
│  │                               │  │                        │  │
│  │  🟡 异常数据确认 (3条)         │  │  🧠 已学习 47 条经验    │  │
│  │     已自动采纳(超时)          │  │  📝 最近: "酸奶品类     │  │
│  │                               │  │  补货偏保守"           │  │
│  └───────────────────────────────┘  └────────────────────────┘  │
│                                                                  │
│  ┌─ Decision History ────────────────────────────────────────┐  │
│  │  日期      场景          决策        回测结果               │  │
│  │  04-17    华北补货      采纳建议     MAPE 9.8% ✅          │  │
│  │  04-10    华东补货      手动调整12个  调整后更优 📈         │  │
│  │  04-03    促销备货      选方案B      缺货率4.2% ⚠️        │  │
│  │  03-27    清仓定价      Agent建议    售罄率91% ✅          │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
Dashboard 技术选型
前端: 单个 HTML + Alpine.js + Tailwind CSS → 零构建
      静态资源已内置于 dashboard/static/（内网部署无需外网 CDN）
通信: SSE (Server-Sent Events) → Agent 实时推送状态
后端: Python stdlib http.server (ThreadingMixIn) → 零外部依赖

部署选项:
  1. 纯 CLI     → 所有交互走终端或消息平台
  2. 文件模式   → Agent 写 JSON，浏览器打开 index.html 轮询
  3. Server模式 → python3 dashboard/server.py，开箱即用
Layer 3: Intelligence
Three-Layer Memory System
┌──────────────────────────────────────────────────────┐
│                 Memory Architecture                   │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Working Memory（工作记忆）                      │  │
│  │  • 当前会话上下文                                │  │
│  │  • 正在处理的数据集状态                           │  │
│  │  • Pipeline 中间结果                             │  │
│  │  生命周期: 单次会话                               │  │
│  └────────────────────────────────────────────────┘  │
│                      ↕ 沉淀                          │
│  ┌────────────────────────────────────────────────┐  │
│  │  Domain Memory（领域记忆）⭐ 供应链特有           │  │
│  │                                                │  │
│  │  📊 数据画像记忆                                 │  │
│  │  "用户A的数据是周粒度, SKU~3000个,              │  │
│  │   生鲜占60%, 历史数据18个月"                     │  │
│  │                                                │  │
│  │  🔧 参数偏好记忆                                 │  │
│  │  "用户A偏好95%服务水平, 安全库存用2σ,            │  │
│  │   上次把Holt-Winters的α调到了0.3"               │  │
│  │                                                │  │
│  │  📈 模型表现记忆                                 │  │
│  │  "饮料品类用EMA比HW好, MAPE低3个点;             │  │
│  │   生鲜品类Croston效果差, 换回MA更稳"            │  │
│  │                                                │  │
│  │  ⚠️ 异常模式记忆                                 │  │
│  │  "每年6月酸奶类有一波促销脉冲,                   │  │
│  │   Q4水果品类需求波动加剧"                        │  │
│  │                                                │  │
│  │  生命周期: 持久化, 按项目/场景隔离                │  │
│  └────────────────────────────────────────────────┘  │
│                      ↕ 提炼                          │
│  ┌────────────────────────────────────────────────┐  │
│  │  Meta Memory（元记忆）                           │  │
│  │  • Skill 使用频率与效果统计                       │  │
│  │  • 用户交互模式（喜欢详细 vs 简洁）               │  │
│  │  • 跨项目通用经验沉淀                             │  │
│  │  生命周期: 永久, Agent 级别                       │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
Learning Loop
  用户发起任务
       │
       ▼
  ┌─────────────┐    记忆检索     ┌──────────────┐
  │ Agent 理解   │───────────────▶│ Memory Store │
  │ 意图         │◀───────────────│              │
  └──────┬──────┘    相关经验     └──────────────┘
         │
         ▼
  ┌─────────────┐
  │ 选择/编排    │ ← 基于历史表现选择最优算法
  │ Skills      │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ 执行 & 输出  │ ← 中间可触发 HITL 审批点
  └──────┬──────┘
         │
         ▼
  ┌─────────────────────────────────────────────┐
  │           Feedback Collection                │
  │                                             │
  │  隐式反馈:                                   │
  │  • 用户是否采纳了建议                         │
  │  • 用户手动调整了哪些参数                     │
  │  • 实际销量 vs 预测值（回溯验证）              │
  │                                             │
  │  显式反馈:                                   │
  │  • 👍👎 评价                                 │
  │  • "这个预测偏高了" 自然语言修正              │
  │  • "下次用XX方法" 直接指令                   │
  └───────────┬─────────────────────────────────┘
              │
              ▼
  ┌─────────────────────────────────────────────┐
  │           Learning Engine                    │
  │                                             │
  │  1. 更新 Domain Memory                       │
  │     (参数偏好、模型表现、异常模式)             │
  │                                             │
  │  2. Skill Self-Improvement                   │
  │     • 记录 "这个品类用method_A比B好"          │
  │     • 自动生成 method selection rules         │
  │                                             │
  │  3. 新 Skill 自动创建                         │
  │     • 用户反复做同一串操作?                    │
  │     • → 提炼成新 Skill + 提交人类审核          │
  │                                             │
  │  4. Backtesting Loop                         │
  │     • 定期用实际数据回测预测准确率              │
  │     • 自动调整算法偏好权重                     │
  └─────────────────────────────────────────────┘
Skill Self-Evolution
每个 Skill 自动维护一份进化档案：

# skills/demand-forecast/evolution.yaml（自动维护）
total_executions: 47
last_updated: 2026-04-24

method_performance:
  holt_winters:
    avg_mape: 12.3%
    best_for: ["饮料", "日化"]
    worst_for: ["生鲜-蔬菜"]
  moving_average:
    avg_mape: 15.1%
    best_for: ["生鲜-蔬菜", "生鲜-水果"]
  croston:
    avg_mape: 18.7%
    best_for: ["低频长尾SKU"]

user_corrections:
  - date: 2026-04-20
    sku_category: "乳制品"
    original: 1200
    corrected: 980
    reason: "用户说618大促结束后需求会回落"
    learned: "大促后一周, 乳制品需求下降约18%"

auto_rules:
  - "生鲜品类默认用 moving_average（基于47次执行的统计）"
  - "促销期间自动切换到 promo-adjusted 模式"
  - "新品前4周用 new-product skill 而非 forecast"
Unified Data Protocol
不同公司、不同系统的数据格式千差万别，但供应链计划的核心数据结构是高度相似的。UDP 是整个框架的基石。

Core Schema
# protocol/supplymind-schema.yaml

sku_master:
  - sku_id: string            # 唯一标识
    name: string              # 品名
    category: string[]        # 多级分类 ["食品", "乳制品", "酸奶"]
    unit: string              # 计量单位
    unit_cost: float          # 单位成本
    unit_price: float         # 零售价
    shelf_life_days: int?     # 保质期（天）
    lead_time_days: float     # 采购提前期（天）
    moq: float?               # 最小起订量
    tags: string[]            # 自定义标签

demand_history:
  - sku_id: string
    location_id: string       # 门店/仓库
    date: date
    quantity: float           # 销售/需求量
    revenue: float?
    is_promo: bool?           # 是否促销期
    stockout_flag: bool?      # 是否缺货（用于修正）

inventory_snapshot:
  - sku_id: string
    location_id: string
    date: date
    on_hand: float            # 在手库存
    in_transit: float?        # 在途库存
    allocated: float?         # 已分配
    available: float          # 可用 = on_hand - allocated

location_master:
  - location_id: string
    name: string
    type: enum[store, dc, factory]
    parent_id: string?        # 上级节点（构建仓网拓扑）
    capacity: float?
    lat: float?
    lon: float?
LLM-Powered Data Adapter
用户原始数据 (CSV / Excel / JSON / 自然语言描述)
        │
        ▼
  ┌─────────────────────┐
  │  data-adapter Skill  │  ← LLM 理解用户数据结构, 映射到标准 Schema
  │                     │  ← 输出 mapping.yaml + 转换后的标准数据
  └──────────┬──────────┘
             ▼
    标准 JSON/Parquet → 可直接喂给任意 Skill
关键设计： data-adapter 会生成一份 mapping.yaml，后续相同格式的数据可以直接复用，无需再次 LLM 推理。

Framework Adapters
SupplyMind 本身不是 Agent 框架，而是被任何框架消费的 Skill 集合。

┌──────────────────────────────────────────────────────────────┐
│                    Framework Adapters                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ OpenClaw     │  │ Hermes       │  │ Claude Code /      │ │
│  │ Adapter      │  │ Adapter      │  │ Generic MCP        │ │
│  │              │  │              │  │                    │ │
│  │ • SKILL.md   │  │ • SKILL.md   │  │ • mcp_server.py   │ │
│  │ • memory →   │  │ • memory →   │  │ • Tool definitions │ │
│  │   catpaw_mem │  │   hermes_mem │  │ • Standard MCP     │ │
│  │ • HITL →     │  │ • HITL →     │  │ • HITL →           │ │
│  │   daxiang/   │  │   telegram/  │  │   stdio prompt     │ │
│  │   message    │  │   gateway    │  │                    │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│                                                              │
│  共享层:                                                     │
│  • core/ 算法引擎 (纯Python, 无框架依赖)                      │
│  • protocol/ 数据协议                                        │
│  • skills/ 业务逻辑                                          │
│                                                              │
│  适配层:                                                     │
│  • adapters/openclaw/  → SKILL.md + CLI wrapper              │
│  • adapters/hermes/    → SKILL.md + memory bridge            │
│  • adapters/mcp/       → MCP server + tool specs             │
│  • adapters/langchain/ → LangChain Tool wrapper (社区贡献)    │
└──────────────────────────────────────────────────────────────┘
每个 Skill 的三种等价调用方式：

# 1. CLI
supplymind demand-forecast --input data.json --horizon 14 --method holt-winters

# 2. Python API
from supplymind.skills.demand_forecast import DemandForecast
result = DemandForecast().run(input_data, horizon=14, method="holt-winters")

# 3. LLM Agent 调用（通过 SKILL.md 触发 / MCP tool call）
Project Structure
supplymind/
├── README.md
├── pyproject.toml
├── LICENSE                          # Apache 2.0
│
├── core/                            # 共享算法引擎（纯Python）
│   ├── timeseries.py                # 时间序列: MA, EMA, HW, STL, Croston
│   ├── inventory_models.py          # 库存模型: EOQ, ROP, (s,S), Newsvendor
│   ├── optimization.py              # 优化: scipy LP, 启发式
│   ├── statistics.py                # 统计: Bootstrap, 异常检测
│   └── classification.py            # 分类: ABC-XYZ, 生命周期
│
├── protocol/                        # 通用数据协议
│   ├── schema.yaml                  # 核心数据 Schema
│   ├── adapter.py                   # LLM 自适应数据转换
│   └── validators.py                # Schema 校验
│
├── memory/                          # 记忆系统
│   ├── working.py                   # 工作记忆（会话级）
│   ├── domain.py                    # 领域记忆（项目级）
│   ├── meta.py                      # 元记忆（Agent级）
│   ├── store.py                     # 存储后端（JSON file / SQLite）
│   └── bridges/                     # 框架记忆桥接
│       ├── openclaw.py
│       ├── hermes.py
│       └── generic.py
│
├── hitl/                            # Human-in-the-Loop 引擎
│   ├── engine.py                    # HITL 核心逻辑
│   ├── confidence.py                # 置信度评估
│   ├── feedback.py                  # 反馈收集
│   └── channels/                    # 交互通道
│       ├── cli.py                   # 终端交互
│       ├── api.py                   # HTTP API（Dashboard用）
│       └── messaging.py             # 消息平台（Telegram/DaXiang等）
│
├── learning/                        # 学习引擎
│   ├── loop.py                      # 学习闭环主逻辑
│   ├── backtest.py                  # 自动回测
│   ├── evolution.py                 # Skill 进化
│   └── skill_generator.py           # 自动 Skill 创建
│
├── skills/                          # 业务 Skills
│   ├── demand/
│   │   ├── forecast/
│   │   │   ├── SKILL.md
│   │   │   ├── main.py
│   │   │   ├── cli.py
│   │   │   ├── schema.py
│   │   │   ├── evolution.yaml       # 自动维护的进化档案
│   │   │   ├── tests/
│   │   │   └── examples/
│   │   ├── anomaly/
│   │   ├── newproduct/
│   │   ├── intermittent/
│   │   ├── decompose/
│   │   └── reconcile/
│   ├── inventory/
│   │   ├── classify/
│   │   ├── safety_stock/
│   │   ├── reorder/
│   │   ├── policy_sim/
│   │   ├── multi_echelon/
│   │   └── newsvendor/
│   ├── pricing/
│   │   ├── markdown/
│   │   ├── lifecycle/
│   │   ├── elasticity/
│   │   └── bundling/
│   ├── fulfillment/
│   │   ├── allocation/
│   │   ├── routing/
│   │   ├── wave/
│   │   └── capacity/
│   └── common/
│       ├── data_profiler/
│       ├── data_adapter/
│       ├── report_generator/
│       └── what_if/
│
├── pipelines/                       # 预置编排流程
│   ├── engine.py                    # Pipeline 执行引擎
│   ├── retail-replenish.yaml
│   ├── markdown-clearance.yaml
│   ├── new-store-launch.yaml
│   └── manufacturing-mrp.yaml
│
├── dashboard/                       # 轻量前端
│   ├── index.html                   # 单文件 (Alpine.js + Tailwind, 800+ lines)
│   ├── server.py                    # stdlib http.server + SSE (零外部依赖)
│   └── static/                      # alpine.js, tailwind.js, chart.js (本地化)
│
├── adapters/                        # 框架适配层
│   ├── openclaw/
│   ├── hermes/
│   ├── mcp/
│   └── langchain/
│
├── datasets/                        # 示例数据集
│   ├── retail_grocery/              # 生鲜零售
│   ├── retail_fmcg/                 # 快消品
│   ├── manufacturing_auto/          # 汽车零部件
│   └── README.md
│
├── docs/                            # 文档
│   ├── getting-started.md
│   ├── architecture.md
│   ├── skill-development-guide.md
│   ├── hitl-design.md
│   ├── memory-system.md
│   └── api-reference.md
│
└── tests/
    ├── core/
    ├── skills/
    ├── memory/
    └── integration/
Skill Specification
每个 Skill 遵循统一规范：

SKILL.md 模板
---
name: demand-forecast
version: 0.1.0
description: 基于历史销售数据生成时序需求预测
triggers:
  - "需求预测"
  - "demand forecast"
  - "预测销量"
  - "下周/下月卖多少"
category: demand
---

# demand-forecast

## 功能
基于历史需求数据，使用统计时序模型生成未来N天的需求预测。

## 输入
- `demand_history`: 历史需求数据（符合 UDP Schema）
- `horizon`: 预测天数（默认14）
- `method`: 预测方法 auto|ma|ema|holt_winters|arima|croston

## 输出
- `forecast`: 逐日/逐周预测值 + 置信区间
- `metrics`: MAPE, MAE, 模型诊断信息
- `recommendation`: 方法选择说明

## CLI
supplymind demand-forecast --input data.json --horizon 14 --method auto

## 示例
见 examples/ 目录
Schema 定义
# skills/demand/forecast/schema.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class ForecastInput:
    demand_history: list[dict]      # UDP demand_history 格式
    horizon: int = 14               # 预测天数
    method: Literal["auto", "ma", "ema", "holt_winters",
                    "arima", "croston"] = "auto"
    confidence_level: float = 0.95  # 置信水平
    frequency: Literal["daily", "weekly", "monthly"] = "daily"

@dataclass
class ForecastOutput:
    forecasts: list[dict]           # [{date, predicted, lower, upper}]
    method_used: str                # 实际使用的方法
    metrics: dict                   # {mape, mae, rmse}
    recommendation: str             # 自然语言建议
    confidence_score: float         # 整体置信度（用于 HITL 判断）
Pipeline Orchestration
Pipeline YAML 规范
name: string                        # 流程名称
description: string                  # 描述
trigger: string                      # 自然语言触发词（正则）
version: string

params:                              # 全局参数
  service_level: 0.95
  forecast_horizon: 14

steps:
  - skill: string                    # Skill 名称
    input: expr                      # 输入（引用上游输出或全局数据）
    params: dict                     # 参数覆盖
    output: $variable                # 输出变量名
    hitl:                            # HITL 配置
      level: auto|review|collaborate
      escalate_if: list[string]      # 升级条件
      show: string                   # 展示给人类的摘要
      actions: list[string]          # 可选操作
      timeout: duration              # 超时自动采纳
      require_approval: bool         # 是否必须审批
    on_error: skip|retry|abort       # 错误处理
    retry: {max: 3, delay: 5s}
预置 Pipelines
Pipeline	场景	包含 Skills
retail-replenish	零售日常补货	profiler → anomaly → forecast → classify → safety-stock → reorder → report
markdown-clearance	临期/滞销出清	profiler → classify → lifecycle → markdown → policy-sim → report
new-store-launch	新店铺货	adapter → newproduct → classify → reorder → allocation → report
manufacturing-mrp	制造业物料需求	adapter → forecast → reconcile → multi-echelon → capacity → report
promo-planning	促销备货	profiler → elasticity → forecast → what-if → reorder → report
Algorithm Design Principles
领域	选用	不选用	理由
时序预测	MA / EMA / Holt-Winters / STL / Croston	深度学习 (LSTM/Transformer)	轻量、可解释、无 GPU 依赖
库存优化	EOQ / ROP / (s,S) / Newsvendor / Monte Carlo	复杂随机规划	经典实用，参数直觉清晰
分类	ABC-XYZ / 生命周期	深度聚类	业务可解释性强
路径优化	最近邻 / 2-opt	精确 TSP 求解器	开源、够用、无外部依赖
线性优化	scipy.optimize.linprog	商业求解器 (Gurobi/COPT)	开源，覆盖 80% 场景
LLM 的角色定位——不替代算法，而是增强编排：

角色	具体工作
数据翻译官	理解用户 CSV/Excel/自然语言，映射到标准 Schema
流程编排者	根据用户意图选择和组合 Skills，构建 Pipeline
结果解读者	将算法输出翻译成业务建议
知识补充者	新品预测时补充品类知识、促销影响估计
What-if 对话	"如果提前期从7天变14天，安全库存增加多少？"
Prophet 作为可选依赖 —— 安装了就用，没装就降级到 Holt-Winters。

Interaction Example
👤 帮我看看下周华北区的补货建议

🤖 正在处理...
   ├── 加载华北区数据（3个仓, 1247个SKU）
   ├── 检测到上周有3个SKU数据异常, 已自动清洗
   ├── 运行需求预测（基于记忆: 华北区用HW效果最好）
   └── 生成补货建议

   📊 华北区下周补货建议:
   ┌─────────────────────────────────┐
   │ 总SKU: 1247  | 需补货: 832     │
   │ 预计金额: ¥215.6万             │
   │ 整体置信度: 87%                 │
   └─────────────────────────────────┘

   ⚠️ 23个SKU需要你关注:
   • 🟡 8个低置信度SKU [查看]
   • 🔴 3个检测到促销影响 [查看]
   • 🟠 12个新品（上市<4周）[查看]

   其余809个SKU补货建议已自动确认。
   [✅ 全部采纳] [📝 逐项审核] [📊 打开Dashboard]

👤 看看那3个促销影响的

🤖 这3个SKU近7天销量突增, 可能是促销驱动:

   | SKU    | 日均(常规) | 日均(近7天) | 我的预测 | 风险           |
   |--------|-----------|------------|---------|----------------|
   | 可乐2L | 120箱     | 340箱      | 180箱   | 促销结束后补多了 |
   | 酸奶X  | 80盒      | 210盒      | 150盒   | 保质期短       |
   | 洗衣液 | 45瓶      | 190瓶      | 100瓶   | 耐存储, 风险低  |

   💡 根据记忆, 上次类似情况（3月水饮促销）你选择了
   "按促销量的70%补货", 效果不错（最终缺货率3%）。
   沿用同样策略吗？

   [🔄 沿用上次策略] [✏️ 自定义] [💬 讨论]

👤 可乐和洗衣液用上次策略，酸奶保守点补100盒

🤖 收到 ✅
   • 可乐2L: 340×70% = 238箱
   • 洗衣液: 190×70% = 133瓶
   • 酸奶X: 100盒（你的手动调整）

   📝 已记录: 你对酸奶品类补货偏保守（第3次下调）,
   下次酸奶类我会默认给出更保守的建议。

   [确认提交] [继续调整]
Roadmap
Phase 1: Foundation（Month 1-2）
 数据协议 (UDP Schema) + data-adapter + data-profiler ✅
 核心算法引擎 (timeseries + inventory_models) ✅
 7 个核心 Skill: data-profiler, demand-anomaly, demand-forecast, inventory-classify, inventory-safety-stock, inventory-reorder, report-generator ✅
 CLI + Python API ✅
 Pipeline 引擎 + YAML 编排 + HITL 标注 ✅
 基础记忆系统 (Working + Domain Memory) ✅
 零售补货 Pipeline 端到端运行 (7/7 步通过, 平均 MAPE 12.8%) ✅
 示例数据集 (91天 × 2门店 × 5 SKU = 910条) ✅
 Live Dashboard (纯 stdlib 后端 + Alpine.js 单文件前端 + SSE) ✅
 HITL 审批 UI — Dashboard 内审批面板（通过/驳回/调整 + SSE 实时刷新）✅
 3 份行业场景数据集（零售生鲜 / 快消品 / 汽车零部件制造）✅
Phase 2: Intelligence（Month 3-4）
 完整需求模块 (anomaly, newproduct, intermittent, reconcile)
 完整库存模块 (safety-stock, policy-sim, multi-echelon, newsvendor)
 Learning Loop + Skill Evolution
 HITL Level 3 (Collaborate) + Feedback Collector
 Meta Memory + 回测系统
 Live Dashboard v1 (文件模式)
 MCP Server 适配
Phase 3: Ecosystem（Month 5-6）
 定价出清模块 (markdown, lifecycle, elasticity)
 履约配送模块 (allocation, routing, wave)
 What-If 多场景对比
 Dashboard v2 (Server模式 + WebSocket)
 OpenClaw / Hermes / Claude Code Adapter 发布
 预置行业模板 (零售/制造/生鲜/医药)
 Skill 自动创建 (从重复操作中提炼)
 社区贡献指南 + Skill 扩展协议
Phase 4: Scale（Month 7+）
 多租户支持
 Skill Marketplace（社区共享 Skill）
 多语言文档 (中/英/日)
 Benchmark 数据集 + 排行榜
 企业版扩展 (权限、审计、SSO)
Contributing
欢迎贡献！SupplyMind 的设计允许你在多个层次参与：

贡献类型	说明
🧮 新算法	在 core/ 中添加新的算法实现
🧩 新 Skill	创建新的业务 Skill（遵循 Skill 规范）
🔗 新 Adapter	适配新的 Agent 框架
📊 数据集	贡献行业数据集到 datasets/
🏭 Pipeline	贡献行业预置流程
📖 文档	改进文档、翻译、教程
🐛 Bug 修复	报告和修复问题
详见 CONTRIBUTING.md

License
Apache License 2.0 — 详见 LICENSE

Core Dependencies
numpy      # 数值计算
pandas     # 数据处理
scipy      # 优化算法
click      # CLI 框架
pydantic   # Schema 校验
可选依赖：

prophet    # 高级时序预测（安装了就用，没装降级到 Holt-Winters）
matplotlib # 服务端图表渲染（Dashboard 备选方案）
Dashboard 后端使用 Python 标准库 http.server，不需要 FastAPI/uvicorn。

SupplyMind — 不做平台，做供应链的瑞士军刀。🔗🧠
