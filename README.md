# ask-data-agent

> 面向电商数据分析的 ReAct Agent，自然语言驱动 SQL 生成、执行与归因分析。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain.com/)
[![Tests](https://img.shields.io/badge/tests-91%20passed-brightgreen.svg)](./tests/)

## 项目概述

面向企业内部 BI 场景的自助式数据分析 Agent。业务人员用自然语言提问，Agent 自动理解意图、查询数据仓库、分析结果、生成回复或结构化报告。全过程在 Thinking Panel 中透明展示。

**核心亮点：**
- **多轮 ReAct 闭环**：UNDERSTAND → REASON → ACT → ANALYZE → CHECK → 没解决? → 回到 REASON（最多 5 轮）
- **自我纠错**：SQL 执行失败 → RAG 诊断 → 函数名自动替换 → 重试（最多 3 次）
- **LLM 判断数据问题**：不是数据分析 → 直接拒绝并告知原因，不浪费 token
- **全过程透明**：Thinking Panel 实时展示每一步的 I/O、耗时、Token 用量
- **中文原生支持**：CJK 分词 + 中英双语 RAG + 中文 UI

## 架构

```
┌─────────────────────────────────────────────────┐
│                    前端 (React + TS)              │
│         Chat Panel  │  Thinking Panel             │
│              WebSocket 全双工流式通信              │
├─────────────────────────────────────────────────┤
│                 服务层 (FastAPI)                   │
│         HTTP POST /chat  │  WS /ws/chat           │
│         POST /api/reports/generate                │
├─────────────────────────────────────────────────┤
│              Agent Runtime (LangGraph)             │
│                                                   │
│   UNDERSTAND → REASON → SQL_EVAL → ACT            │
│      ↕ CLARIFY    ↕ REFLECT    ↕ DEGRADE           │
│      → RESULT_EVAL → ANALYZE → CHECK              │
│           ↑                    ↓                  │
│           └── 没解决，再来一轮 ←──┘ (最多 5 轮)      │
│           → OUTPUT_EVAL → END                     │
│                                                   │
│   横切: ThinkingTracer · MetricsCollector          │
├─────────────────────────────────────────────────┤
│    RAG (5 KB)     │  Evaluator (3 道门禁)          │
│    · Schema KB    │  · Gate 1: SQL 安全            │
│    · Business KB  │  · Gate 2: 结果质量            │
│    · Fix KB       │  · Gate 3: 输出幻觉检测        │
│    · Analytics KB │                                 │
│    · Eval KB      │  规则引擎 + 硬校验              │
├─────────────────────────────────────────────────┤
│   LLM Provider   │  DW Connector  │  Memory        │
│   DeepSeek/Qwen  │  DuckDB(dev)   │  File/Redis    │
│   /GLM           │  ClickHouse*   │  Session Store │
├─────────────────────────────────────────────────┤
│              数据层                                │
│   DuckDB (Olist)  │  ChromaDB  │  PostgreSQL*      │
│   9 表 150万行     │  83 docs   │  报告/用户        │
└─────────────────────────────────────────────────┘
```

## 数据集

[Olist Brazilian E-commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — 9 张表，150 万行，2016-2018：

| 表 | 行数 | 说明 |
|----|------|------|
| customers | 99,441 | 客户（城市/州/邮编） |
| orders | 99,441 | 订单（时间/状态/交付） |
| order_items | 112,650 | 订单明细（价格/运费/商品/卖家） |
| order_payments | 103,886 | 支付（类型/分期/金额） |
| order_reviews | 99,224 | 评论（评分/内容） |
| products | 32,951 | 商品（品类/重量/尺寸） |
| sellers | 3,095 | 卖家（城市/州） |
| geolocation | 1,000,163 | 地理坐标 |
| category_translation | 71 | 品类翻译（葡→英） |

## 快速启动

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 下载数据（需要 Kaggle API）
python scripts/setup_data.py

# 3. 复制 .env 文件，填入 DeepSeek API Key
cp .env.example .env

# 4. 启动后端
python scripts/start_backend.py

# 5. 新终端，启动前端
cd web && npm install && npm run dev

# 6. 打开浏览器
http://localhost:5173
```

## 测试

```bash
# 全部测试（91 条，3 分钟）
pytest tests/ -v

# 仅单元测试（79 条，<2 秒）
pytest tests/unit/ -v

# 集成测试（mock LLM + 真实 DW，32 秒）
pytest tests/integration/ -v

# 100 条全链路基准（需要真实 API）
python -m tests.run_100
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | React + TypeScript + Vite | Chat + Thinking 双面板 |
| 图表 | ECharts | 可交互图表 |
| 后端 | FastAPI (Python) | HTTP + WebSocket |
| Agent | LangGraph | 状态机编排 |
| SQL 生成 | 原生 Prompt + LLM | 不依赖 LangChain SQL Toolkit |
| LLM | DeepSeek / Qwen / GLM | 可插拔适配器 |
| 向量库 | ChromaDB + multilingual-MiniLM | 384 维双语嵌入 |
| 数据仓库 | DuckDB | 单机文件，零依赖 |
| 缓存 | Redis (可选) | 会话记忆 |
| 日志 | Python logging | 按天归档 |

## 目录结构

```
ask-data-agent/
├── agent/                  # Agent 核心
│   ├── graph.py            # 状态机定义（13 节点）
│   ├── state.py            # AgentState Schema
│   └── nodes/              # 各节点实现
│       ├── understand.py   # 意图解析 + 数据问题判断
│       ├── reason.py       # SQL 生成
│       ├── act.py          # SQL 执行
│       ├── reflect.py      # 错误诊断 + 直接修正
│       ├── analyze.py      # 分析 + 图表
│       ├── check.py        # 回答质量检查（多轮回路）
│       ├── clarify.py      # 反问澄清
│       ├── degrade.py      # 降级输出
│       └── escalate.py     # 转人工 + 调整建议
├── evaluator/              # 质量门禁
│   ├── rules.py            # 规则引擎
│   ├── judge.py            # LLM Judge
│   └── gates/              # 三道门禁
├── rag/                    # 动态 RAG
│   ├── router.py           # 四阶段策略分发
│   ├── embedding.py        # 嵌入模型
│   ├── strategies/         # 检索策略
│   └── knowledge/          # 5 个知识库
├── memory/                 # 记忆管理
│   ├── session.py          # 会话记忆
│   └── context.py          # 上下文窗口
├── monitoring/             # 横切关注点
│   ├── tracer.py           # 思考过程追踪
│   ├── logger.py           # 结构化日志
│   └── metrics.py          # 指标收集
├── prompts/                # Prompt 模板
│   ├── manager.py
│   ├── templates/          # 12 个 Jinja2 模板
│   └── config/
├── connectors/             # 可插拔连接器
│   ├── llm/                # LLM Provider
│   └── dw/                 # DW Connector
├── report/                 # 报告引擎
│   ├── planner.py
│   ├── assembler.py
│   └── renderer.py
├── api/                    # FastAPI
│   ├── main.py
│   ├── routes/             # chat / report
│   └── ws.py               # WebSocket
├── web/                    # React 前端
├── tests/                  # 91 条测试
├── config/                 # 配置文件
├── data/                   # DuckDB + ChromaDB
└── scripts/                # 启动/数据脚本
```

## 设计决策

**为什么 LangGraph 而不是自己写状态机？**
13 个节点的条件路由（reject→retry / reflect→fix / degrade→analyze），手动维护 if-else 很快失控。LangGraph 提供的 `StateGraph` + `conditional_edges` 让路由逻辑与节点逻辑分离，每个节点只需关心自己的输入输出。

**为什么不用多 Agent 架构？**
当前 13 个节点共享一个 `AgentState`，没有 Agent 间通信开销。多 Agent 的价值在于独立替换子模块（比如换更强的 SQL Agent），但目前只用一个 LLM，拆了反而增加延迟。

**为什么 ChromaDB 不做文档切片？**
Schema KB 里一条文档就是一张表定义（"Table orders: order_id (VARCHAR)..."），Business KB 里一条就是一个业务指标（"GMV = SUM(price)"）。每条都是最小语义单元，切了反而破坏语义完整性。

**为什么 CHECK 和 REFLECT 分开，不在 REFLECT 里做？**
REFLECT 修的是语法错误（字段名不存在、函数名写错），做确定性替换后直接跑。CHECK 修的是思路问题（分析不够深入、缺少归因下钻），需要 LLM 判断"问题真的回答完了吗"。两者判断逻辑完全不同，揉在一起 LLM 会分心。

**为什么不用 LLM Judge？**
规则引擎（SELECT 检查、LIMIT 检查、注入检测）覆盖了所有安全场景。LLM Judge 加了 3 次额外 API 调用，还曾经把正确 SQL 判为低分导致误升级。当前结论：规则引擎足够，LLM 评分不必要。

## 许可证

MIT
