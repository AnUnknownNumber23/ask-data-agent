# ask-data-agent — 数据分析 Agent 系统

## 项目概述

面向电商数据分析的 ReAct Agent，支持自然语言查询数据库、自动归因分析、趋势预测。150 万行真实数据，11 节点状态机，中英文双语，Web 全栈。

**核心亮点：** 多轮 ReAct 自修正闭环 · 非数据问题自动拒绝 · 每一步思考过程透明可视 · 91 条测试 0 失败。

## 技术栈

`Python` `FastAPI` `LangGraph` `React` `TypeScript` `DuckDB` `ChromaDB` `ECharts` `WebSocket` `DeepSeek API` `Sentence-Transformers`

## 我的贡献

**架构设计**

- 独立设计并实现了完整的 11 节点 LangGraph 状态机，包括意图解析、SQL 生成、安全校验、执行、错误诊断、分析、幻觉检测、归因下钻、趋势预测
- 引入多轮 ReAct 循环——CHECK 节点评估"问题是否真的被回答了"，未解决则自动回到 REASON 进行下一轮推理，替代传统的线性流水线
- 设计四阶段动态 RAG 检索策略：UNDERSTAND(语义发现)、REASON(上下文补充)、REFLECT(精确纠错)、ANALYZE(领域知识)，不同阶段切换不同的向量/关键词/元数据权重

**自我纠错**

- 实现 REFLECT 节点：SQL 执行失败时，不依赖 LLM 二次推理，通过 Fix KB + Schema KB 关键词搜索直接替换错误字段名/函数名，绕过 LLM 的顽固性错误再生
- 设计三道门禁评估体系：SQL 安全规则引擎(毫秒级)、结果质量检查(行数/空值/聚合判断)、输出幻觉硬校验(数值是否在原始结果集中)

**非数据问题检测**

- 让 UNDERSTAND 节点的 LLM 输出 `is_data_question` 字段，非数据问题直接拒绝并告知原因，不浪费后续 token
- 比关键词黑名单更准确——能正确区分"帮我写代码"(拒绝)和"帮我写 SQL 查订单"(放行)

**工程实践**

- 前端 WebSocket 全双工流式通信，Thinking Panel 实时展示每一步 I/O、耗时、Token 用量
- embedding 从 SHA-256 哈希升级为 multilingual-MiniLM-L12-v2，中英文跨语言语义检索
- 91 条测试(79 单元 + 12 集成)，100 条全链路基准 100% 通过
- 结构化日志覆盖全部节点，按天归档

## 项目数据

- 77 次提交，148 文件，89 个 Python 文件
- 数据集: Olist Brazilian E-commerce，9 表 150 万行
- 91 条测试，3 分钟跑完，0 失败
- 100 条全链路基准，100% 通过，平均 5.7s

## 面试问答准备

**Q: 为什么用 LangGraph 而不是自己写状态机？**
A: 11 个节点的条件路由(reject→retry / reflect→fix / check→reason)如果手动用 if-else 维护，路由逻辑会分散在 10+ 个文件里。LangGraph 的 StateGraph + conditional_edges 让路由声明式定义在 graph.py 里，每个节点只关心自己的输入输出。权衡是增加了一个依赖(LangGraph ≈ 500KB)，但省掉了自己维护状态机基础设施的成本。

**Q: 为什么不用多 Agent 架构？**
A: 当前 11 个节点共享一个 AgentState，没有 Agent 间通信开销。多 Agent 的价值在于独立替换子模块(比如换更强的 SQL 生成模型)，但目前只用 DeepSeek 一个模型，拆了反而增加延迟。等遇到单 Agent 解决不了的问题(比如要同时查询 DuckDB 和 PostgreSQL 再做融合)再做。

**Q: 为什么不切 ChromaDB 文档？**
A: Schema KB 里一条文档就是一张表定义("Table orders: order_id VARCHAR...")，Business KB 里一条就是一个业务指标("GMV = SUM(price)")。每条都是最小语义单元，切了反而破坏完整性。对 83 条文档的规模来说，不需要切片。

**Q: REFLECT 为什么不走 REASON 再生成一遍？**
A: 实测发现 LLM 会固执地把用户 query 里的函数名(如 DATE_FORMAT)再写回 SQL 里——怎么引导都没用。所以 REFLECT 做确定性字符串替换后直接跑 SQL_EVAL 验证，跳过 REASON。这是实践得出的设计决策，不是理论上的"正确做法"。

**Q: 最大的技术难点是什么？**
A: LLM 生成 SQL 的不可靠性。同一条提示词，LLM 可能生成正确 SQL，也可能在 SQL 外加 ```json 标记导致解析失败，还可能固执地使用 DuckDB 不支持的函数。我花了大量精力在容错上——_extract_sql 函数处理 4 种可能的包裹格式，REFLECT 直接替换已知的函数名差异，SQL_EVAL 提供最后一道语法防线。

**Q: 如果再给你两周，你会做什么？**
A: 1) 把报告生成的 Planner 也纳入 ReAct 循环，让报告质量从"生成"变成"迭代优化"；2) 加一个 SQL 缓存层——相同语义的查询直接复用，减少 LLM 调用；3) 接入真实 BI 工具的 embedding 评测框架，用 recall@k 指标量化 RAG 质量改进。
