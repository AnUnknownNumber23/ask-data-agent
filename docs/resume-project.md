# ask-data-agent - 电商数据分析 Agent 系统

## 简历项目经历

**ask-data-agent | 自纠错数据分析 Agent**  
`Python` `FastAPI` `LangGraph` `DuckDB` `ChromaDB` `React` `TypeScript` `WebSocket` `DeepSeek API` `Jinja2`

面向企业 BI 场景的自然语言数据分析 Agent。用户用中文或英文提问后，系统自动完成意图理解、RAG 检索、SQL 生成、安全校验、查询执行、结果分析和可视化回复，并通过前端 Thinking Panel 实时展示 Agent 每一步的输入输出、耗时和 Token 用量。项目基于 Olist 电商数据集，覆盖 9 张业务表和约 150 万行数据。

- 设计并实现 12 节点 LangGraph 状态机，将 `UNDERSTAND -> REASON -> SQL_EVAL -> ACT -> RESULT_EVAL -> ANALYZE -> CHECK -> OUTPUT_EVAL` 等步骤拆成可独立测试的节点，并通过条件路由支持拒答、澄清、降级、重试和人工升级。
- 构建多轮 ReAct 自修正闭环：`CHECK` 节点判断“当前回答是否真正解决问题”，未完成时自动回到 `REASON` 继续下钻分析，最多 5 轮，避免传统线性 SQL Bot 只查一次就结束。
- 实现 SQL 错误自修复链路：SQL 执行失败后进入 `REFLECT`，结合 Fix KB 和 Schema KB 识别字段名、函数名、表结构错误，并直接回到 `SQL_EVAL` 验证修复结果，最多自动重试 3 次。
- 设计四阶段动态 RAG 策略：在 `UNDERSTAND`、`REASON`、`REFLECT`、`ANALYZE` 阶段分别切换语义发现、上下文补充、精确纠错、领域分析知识检索；离线评估整体 recall 达 83.5%，其中 UNDERSTAND / REASON 阶段 recall 分别为 89.3% / 92.8%。
- 建立三道 Evaluator 闸门：执行前校验 SQL 只读、安全和 LIMIT；执行后检查空结果、异常行数和结果质量；输出前校验回答中的数值是否来自原始结果集，降低 SQL 注入、无效查询和幻觉结论风险。
- 在 `UNDERSTAND` 阶段引入 `is_data_question` 判断，非数据分析问题直接拒答并说明原因，避免后续 SQL 生成和数据库查询浪费 Token。
- 封装可插拔 LLM Provider 和 DW Connector，支持 DeepSeek/Qwen/GLM 模型适配，以及 DuckDB 开发数据仓库；Prompt 使用 Jinja2 模板集中管理，便于版本化和复用。
- 实现 FastAPI + WebSocket 后端和 React + TypeScript 前端，前端双面板展示对话结果与 Agent 推理过程，支持 SQL、查询结果、评估状态、错误重试记录的实时流式展示。
- 完成 91 条自动化测试，包括 Agent 节点、RAG Router、Prompt Manager、Evaluator 规则、会话上下文和 DW Connector 集成测试；构建 100 条端到端问题评估集，综合得分 0.832、回答质量得分 0.908，平均响应 7.6s。

**项目成果**

- 将自然语言查数流程从“人工理解需求、编写 SQL、解释结果”封装为可追踪的 Agent 工作流。
- 用 LangGraph 条件路由把复杂 Agent 行为显式化，降低节点逻辑和流程编排耦合度。
- 通过规则 Evaluator + RAG 自修复减少 LLM 生成 SQL 的不确定性，提高失败可诊断性。
- 形成完整的工程闭环：后端 API、WebSocket 流式过程展示、可插拔模型/数据仓库、结构化日志和自动化测试。

## 简历压缩版

可直接放到一页简历里的版本：

**自纠错数据分析 Agent | Python / FastAPI / LangGraph / RAG / DuckDB / React**

- 独立设计并实现面向电商 BI 的自然语言数据分析 Agent，基于 Olist 9 表约 150 万行数据，支持中文/英文提问、自动生成 SQL、执行查询、结果分析和可视化回复。
- 基于 LangGraph 编排包含理解、推理、执行、反思、评估和降级处理的多阶段 Agent 工作流，构建多轮 ReAct 自我修正机制；当 SQL 校验失败、执行报错、结果质量不足或回答未完成时，通过条件路由自动回到推理/反思节点，支持最多 5 轮下钻分析。
- 设计动态 RAG 检索体系，在理解、推理、纠错、分析阶段分别检索 Schema、业务指标、修复规则和分析方法知识库；离线评估整体 recall 83.5%。
- 构建 SQL/结果/输出三道 Evaluator 闸门，校验只读 SQL、LIMIT、空结果、异常结果和回答数值来源，降低 SQL 注入、无效查询和幻觉结论风险。
- 实现 FastAPI + WebSocket + React Thinking Panel，实时展示 Agent 每一步 I/O、耗时、Token、SQL、结果和重试记录；100 条端到端评估综合得分 0.832，回答质量得分 0.908。

## 系统评估指标

这些指标适合放在项目详情或面试材料里，简历正文可按空间选择保留：

- **端到端评估**：100 条自然语言问题，覆盖统计、排行、趋势、过滤、复杂 JOIN、归因、预测和边界问题；综合得分 0.832，SQL 得分 0.756，回答质量得分 0.908，平均响应 7.6s。
- **RAG 评估**：整体 recall 83.5%、precision 63.2%；UNDERSTAND 阶段 recall 89.3%，REASON 阶段 recall 92.8%，ANALYZE 阶段 recall 100%。
- **异常处理**：100 题评估中包含 18 次澄清、1 次升级，说明系统能够对信息不足、Schema 不匹配或超出能力范围的问题进行可解释处理。
- **测试覆盖**：91 条自动化测试覆盖 Agent 节点、RAG Router、Prompt Manager、Evaluator、上下文管理和 DW Connector 集成链路。

## 面试讲解提纲

**1. 这个项目解决什么问题？**

传统 BI 查询需要业务人员找数据分析师写 SQL，沟通成本高，而且查询过程不可追踪。这个项目把“理解业务问题 -> 找表和字段 -> 写 SQL -> 查数 -> 解读结果 -> 生成图表/报告”封装成一个可追踪、可纠错的数据分析 Agent，让业务问题可以直接用自然语言驱动。

**2. 为什么用 LangGraph？**

项目不是简单的“用户问题 -> LLM -> SQL -> 结果”，而是有拒答、澄清、SQL 安全校验、执行失败反思、空结果重试、输出质量检查等分支。如果用普通 if-else，流程会散落在多个节点里。LangGraph 的 `StateGraph` 和 `conditional_edges` 可以把流程编排集中定义在 `agent/graph.py`，每个节点只处理自己的输入输出。

**3. ReAct 闭环怎么做？**

核心路径是 `REASON -> SQL_EVAL -> ACT -> RESULT_EVAL -> ANALYZE -> CHECK`。如果 SQL 不安全，回到 `REASON` 重写；如果执行报错，进入 `REFLECT` 修复；如果结果为空或质量差，回到 `REASON` 放宽条件或换查询；如果 `CHECK` 判断问题没回答完，再进入下一轮下钻。

**4. REFLECT 为什么不直接让 LLM 重写 SQL？**

实测中，LLM 容易重复犯同类错误，比如持续使用 DuckDB 不支持的函数或不存在的字段。REFLECT 更适合做确定性修复：从错误信息中识别字段名、函数名和表名，再结合 Fix KB/Schema KB 做替换，修完直接回 `SQL_EVAL` 验证，减少“重新生成又犯错”的概率。

**5. RAG 在项目里不是简单知识库问答，而是分阶段检索。**

- `UNDERSTAND`：找相关表、业务指标和问题类型。
- `REASON`：补充字段、JOIN 关系、时间字段和 SQL 约束。
- `REFLECT`：针对报错做精确字段/函数修复。
- `ANALYZE`：补充趋势、排行、分布、归因等分析方法。

**6. Evaluator 怎么降低风险？**

SQL Evaluator 保证只执行 SELECT，禁止 DDL/DML，并强制 LIMIT；Result Evaluator 检查空结果、异常行数和结果质量；Output Evaluator 检查回答里的数字是否能在原始结果集中找到，避免模型编造结论。

**7. 项目最难的地方是什么？**

LLM 生成 SQL 的不确定性。它可能输出 Markdown 包裹的 SQL、使用错误函数、遗漏 LIMIT，或者在结果不足时给出过度结论。这个项目的重点不是“调用一次 LLM”，而是用状态机、RAG、规则校验、反思修复和前端可观测性，把不确定的 LLM 输出约束成可诊断、可恢复的工程流程。

**8. 如果继续迭代，会怎么做？**

- 引入 SQL 语义缓存，相同意图直接复用已验证 SQL，减少 LLM 调用。
- 为 RAG 增加更严格的 recall@k 评估集，持续优化 Schema/Business/Fix KB。
- 把报告 Planner 纳入 ReAct 闭环，让报告生成也支持质量检查和迭代优化。
- 接入真实企业数仓权限系统，增加行列级权限和审计日志。
