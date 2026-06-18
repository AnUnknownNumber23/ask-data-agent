# ask-data-agent — 实施计划

> 日期: 2026-06-18  
> 关联设计: [2026-06-18-data-analysis-agent-design.md](2026-06-18-data-analysis-agent-design.md)  
> 状态: v1 基本完成，待审核收尾

---

## 当前完成度

### ✅ 已完成

| 模块 | 内容 | 状态 |
|------|------|------|
| **Agent 状态机** | 11 节点 LangGraph (8 agent + 3 evaluator gates) | ✅ |
| **LLM Provider** | DeepSeek / Qwen / GLM 适配器 + 配置驱动 | ✅ |
| **DW Connector** | DuckDB + Olist 9 表数据集 | ✅ |
| **RAG** | 四阶段策略 + Schema KB + Business KB + Fix KB | ✅ |
| **Evaluator** | 三道门禁 (SQL / Result / Output) + 规则引擎 | ✅ |
| **Prompt Manager** | 9 个 Jinja2 模板 + YAML 元信息配置 | ✅ |
| **Memory** | 上下文窗口管理 (摘要/截断/Token 预算) | ✅ |
| **Thinking Tracer** | 每步 I/O 序列化 + WebSocket 实时推送 | ✅ |
| **Report Engine** | Planner + Assembler + Renderer + 3 个 JSON 模板 | ✅ |
| **FastAPI** | HTTP POST /chat + WebSocket /ws/chat + /api/health | ✅ |
| **Frontend** | React + ChatPanel + ThinkingPanel + useWebSocket hook | ✅ |
| **Docker Compose** | 7 服务 (nginx/frontend/backend/redis/chromadb/postgres/llm-proxy) | ✅ |
| **数据** | Olist DuckDB 数据库 + 下载脚本 | ✅ |
| **测试** | 单元测试 (rules/rag/prompts/context/llm) + 集成测试 (dw) | ✅ |

### ⚠️ 需修复/补完

| 项 | 说明 | 优先级 |
|----|------|--------|
| **LLM Judge** | Evaluator 的 LLM Judge 部分未实现（目前只有规则引擎） | P1 |
| **会话记忆 (Redis)** | 代码中 Redis 配置已有但未实际接入会话持久化 | P1 |
| **鉴权** | JWT middleware 已写但未启用 | P2 |
| **限流** | 未实现 | P2 |
| **ChromaDB → Milvus** | v1 用 ChromaDB PersistentClient，生产需迁移 | P2 |
| **E2E 测试** | verify_e2e.py 脚本存在但未集成到 CI | P2 |
| **Analytics KB** | 设计文档规划但未实现（analyze 节点只有框架） | P3 |
| **Eval KB** | 设计文档规划但未实现 | P3 |

---

## 近期待办 (P1)

### 1. LLM Judge 补完

```
evaluator/
├── rules.py          # ✅ 规则引擎已完成
└── judge.py          # ❌ 未实现 — LLM Judge 评分
    └── gates/
        ├── sql_eval.py     # 补: 小模型评估 SQL 语义 vs 意图
        ├── result_eval.py  # 补: 评估结果相关性
        └── output_eval.py  # 补: 幻觉检测 (结论数值 vs 原始数据)
```

### 2. 会话记忆持久化 (Redis)

```
memory/
├── context.py        # ✅ 上下文窗口管理
└── session.py        # ❌ 未实现 — Redis 会话持久化
    - 多轮对话历史存取
    - 会话 TTL 过期
    - 修正记录累积
```

### 3. 前端完善

```
web/src/
├── panels/
│   ├── ChatPanel/    # ⚠️ 流式渲染未实现 (当前等全部完成才显示)
│   └── ThinkingPanel/ # ⚠️ Trace 增量更新未实现
└── services/         # ❌ HTTP fallback 未实现
```

---

## v2 规划

| 模块 | 内容 | 预估工作量 |
|------|------|-----------|
| 归因分析 | 自动维度下钻、多因素归因 | 2-3 周 |
| 定时报告 | Cron 触发 + 企微/邮件推送 | 1-2 周 |
| AI 自主编排报告 | 完全动态章节生成 | 2 周 |
| Milvus 升级 | ChromaDB → Milvus 分布式 | 1 周 |
| 多租户 | 租户隔离 + 列级权限 | 2-3 周 |
| 预测分析 | 趋势预测 + 异常检测 | 2 周 |
| K8s 部署 | Docker Compose → K8s | 1-2 周 |

---

## 测试补完计划

```
tests/
├── unit/
│   ├── test_rules.py           # ✅
│   ├── test_rag_router.py      # ✅
│   ├── test_prompt_manager.py  # ✅
│   ├── test_context.py         # ✅
│   ├── test_llm_provider.py    # ✅
│   ├── test_rag_strategies.py  # ❌ 需补
│   ├── test_judge.py           # ❌ 需补 (依赖 LLM Judge)
│   └── test_session.py         # ❌ 需补 (依赖 Redis Session)
├── integration/
│   ├── test_dw_connector.py    # ✅
│   ├── test_agent_graph.py     # ❌ 需补 (依赖 Mock LLM)
│   └── test_api.py             # ❌ 需补 (FastAPI TestClient)
└── fixtures/
    ├── mock_llm.py             # ✅
    └── olist_sample.sql        # ✅
```
