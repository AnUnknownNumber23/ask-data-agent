# ask-data-agent

> 基于 ReAct 架构的电商数据分析 Agent — 自然语言驱动 SQL 生成、执行、归因分析与趋势预测。

[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-ff6f00)](https://langchain.com/)
[![Tests](https://img.shields.io/badge/tests-90%20passed-brightgreen)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 项目简介

面向企业内部 BI 场景的自然语言数据分析 Agent。用户用中英文提问，系统自动完成意图理解、RAG 检索、SQL 生成、安全校验、查询执行、结果分析和图表生成。全过程通过 Thinking Panel 实时展示每一步的输入输出、耗时和 Token 用量。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 描述性分析 | 自然语言 → SQL → 数据 → 图表，支持统计、排序、过滤、时间序列 |
| 归因分析 | 问"为什么"时自动拆维度下钻，定位根因 |
| 预测分析 | 趋势外推 + 环比异常预警 |
| 报告生成 | 模板驱动，Markdown 导出 |
| 自我纠错 | SQL 执行失败 → RAG 诊断 → 函数名自动替换 → 重试（最多 3 次） |
| 多轮 ReAct | CHECK 节点判断"问题回答完了吗"，未完成则自动开启下一轮分析 |
| 非数据问题拒绝 | LLM 判断问题是否可答，不可答则告知原因 |

## 快速启动

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 下载 Olist 数据集（需 Kaggle API）
python scripts/setup_data.py

# 3. 配置 DeepSeek API Key
cp .env.example .env          # 编辑 .env 填入 DEEPSEEK_API_KEY

# 4. 启动后端（自动清理端口 + 热重载）
python scripts/start_backend.py

# 5. 启动前端
cd web && npm install && npm run dev

# 6. 打开 http://localhost:5173
```

## 架构

```
用户提问
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent Runtime (LangGraph)               │
│                                                          │
│  UNDERSTAND (意图解析 + 数据问题判断)                       │
│      │                                                   │
│      ├── 不是数据问题 → 拒绝 + 告知原因                      │
│      ├── 无匹配 → CLARIFY (反问)                           │
│      └── 匹配到表 → 进入 ReAct 循环                        │
│                                                          │
│  ┌──── ReAct 循环（最多 5 轮）────────────────────────┐    │
│  │  REASON (写 SQL) → SQL_EVAL (安检) → ACT (执行)    │    │
│  │    ↕ REFLECT (执行失败时自动修正)                      │    │
│  │    → RESULT_EVAL (空结果重试)                         │    │
│  │    → ANALYZE (生成解读 + 图表)                        │    │
│  │    → CHECK (问题回答完了吗？)                          │    │
│  │      ├── 没完 → 回 REASON 下一轮                      │    │
│  │      └── 完了 → OUTPUT_EVAL (幻觉校验) → 输出          │    │
│  └────────────────────────────────────────────────────┘    │
│                                                          │
│  横切: ThinkingTracer (每步 I/O + 实时推送)                │
├─────────────────────────────────────────────────────────┤
│  RAG (5 KB)          │  Evaluator (3 Gates)              │
│  Schema / Business   │  Gate 1: SQL 安全 (注入/LIMIT)     │
│  / Fix / Analytics   │  Gate 2: 结果质量 (空值/截断)      │
│  / Eval              │  Gate 3: 输出幻觉 (数值溯源)       │
├─────────────────────────────────────────────────────────┤
│  LLM Provider        │  DW Connector     │  Memory       │
│  DeepSeek/Qwen/GLM   │  DuckDB           │  Session Store│
├─────────────────────────────────────────────────────────┤
│  数据层                                                │
│  DuckDB (Olist 9表 150万行) │ ChromaDB (119 docs)       │
└─────────────────────────────────────────────────────────┘
```

## 数据集

[Olist Brazilian E-commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — 巴西最大电商平台的真实订单数据，时间跨度 2016-09 至 2018-10。

| 表 | 行数 | 说明 |
|----|------|------|
| orders | 99,441 | 订单（时间/状态/交付） |
| order_items | 112,650 | 订单明细（价格/运费/商品/卖家） |
| order_payments | 103,886 | 支付（类型/分期/金额） |
| order_reviews | 99,224 | 评论（评分/内容） |
| customers | 99,441 | 客户（城市/州/邮编） |
| products | 32,951 | 商品（品类/重量/尺寸） |
| sellers | 3,095 | 卖家（城市/州） |
| geolocation | 1,000,163 | 地理坐标 |
| category_translation | 71 | 品类翻译（葡萄牙语→英语） |

## 性能评估

| 指标 | 数据 |
|------|------|
| 100 条端到端评估 | **总得分 83.2%** |
| 基础统计查询 | 99.3% |
| 时间序列 | 93.0% |
| 条件过滤 | 93.7% |
| 复杂多表 JOIN | 69.0% |
| 归因分析 | 64.0% |
| RAG 语义召回率 | **84%** (UNDERSTAND 89%, REASON 93%) |
| 平均响应时间 | 5.7 秒 |

## 测试

```bash
# 全部测试（90 条，3 分钟）
pytest tests/ -q

# 单元测试（78 条，< 2 秒）
pytest tests/unit/ -q

# 集成测试（mock LLM + 真实 DW，32 秒）
pytest tests/integration/ -q

# RAG 召回评估（50 条标注查询）
python tests/eval_rag_recall.py

# 端到端评估（100 条标注查询，需真实 API）
python tests/eval_100.py
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React + TypeScript + Vite + ECharts |
| 后端 | FastAPI + WebSocket |
| Agent | LangGraph (11 节点状态机) |
| LLM | DeepSeek (默认) / Qwen / GLM |
| 数据仓库 | DuckDB |
| 向量库 | ChromaDB + multilingual-MiniLM-L12-v2 |
| Embedding | Sentence-Transformers (384 维) |
| 记忆 | 文件存储 / Redis (可选) |
| 日志 | Python logging (按天归档) |
| 报告 | Jinja2 模板 + ReportLab |

## 目录结构

```
ask-data-agent/
├── agent/                  # Agent 核心
│   ├── graph.py            # LangGraph 状态机 (11 节点)
│   ├── state.py            # AgentState Schema
│   └── nodes/              # 节点实现
│       ├── understand.py   # 意图解析 + 数据问题判断
│       ├── reason.py       # 意图 → SQL
│       ├── act.py          # SQL 执行
│       ├── reflect.py      # 错误诊断 + 直接修正
│       ├── analyze.py      # 解读 + 图表
│       ├── check.py        # 回答质量检查 (多轮回路)
│       ├── clarify.py      # 反问澄清
│       └── escalate.py     # 转人工 + 调整建议
├── evaluator/              # 质量门禁
│   ├── rules.py            # 规则引擎 (注入/LIMIT)
│   ├── judge.py            # LLM Judge (已禁用)
│   └── gates/              # 三道闸门
├── rag/                    # 动态 RAG
│   ├── router.py           # 四阶段策略分发
│   ├── embedding.py        # 嵌入模型封装
│   ├── strategies/         # 检索策略
│   └── knowledge/          # 5 个知识库
├── memory/                 # 会话记忆
├── monitoring/             # Tracer + Logger
├── prompts/                # Jinja2 模板 (11 个)
├── connectors/             # 可插拔 LLM/DW
├── report/                 # 报告引擎
├── api/                    # FastAPI + WebSocket
├── web/                    # React 前端
├── tests/                  # 90 条测试
├── config/                 # config.yaml
└── data/                   # DuckDB + ChromaDB
```

## 设计决策

**为什么 LangGraph？**
11 个节点的条件路由（reject → retry / reflect → fix / check → reason），手动 if-else 会散落在多个文件里。StateGraph + conditional_edges 让路由声明式定义，每个节点只管自己的输入输出。

**为什么不是多 Agent？**
共享一个 AgentState，没有 Agent 间通信开销。多 Agent 在有多个独立可替换子模块时才有价值，当前一个 LLM 足够。

**为什么 CHECK 和 REFLECT 分开？**
REFLECT 修语法错误（字段不存在、函数写错），做确定性替换后直接跑。CHECK 修思路问题（分析不够深入、缺少下钻），需要 LLM 判断"回答完了吗"。逻辑不同，分开各司其职。

**为什么 ChromaDB 不做文档切片？**
Schema KB 一条就是一张表定义，Business KB 一条就是一个业务指标。每条都是最小语义单元，切了反而破坏完整性。119 条文档不需要切片。

**为什么不用 LLM Judge？**
规则引擎（SELECT/LIMIT/注入检测）覆盖了所有安全场景。LLM Judge 曾把正确 SQL 判低分导致误升级。当前结论：规则引擎足够。

## License

MIT
