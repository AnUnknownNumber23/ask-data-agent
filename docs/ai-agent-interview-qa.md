# AI 应用开发 / AI Agent 面试问答

> 适用方向：AI Agent 应用开发、大模型应用开发、LLM 后端开发、自然语言数据分析系统  
> 项目依据：`ask-data-agent`、简历项目“电商数据分析 Agent”

## 1. 自我介绍与项目总览

### Q1：请做一个 1 分钟自我介绍。

我叫刘志勇，本科是计算机科学与技术，求职方向是 AI Agent 应用开发。我的主要项目是一个面向电商 BI 场景的自然语言数据分析 Agent，用户用中文或英文提问后，系统会自动完成意图理解、RAG 检索、SQL 生成、安全校验、查询执行、结果分析和可视化回复。

这个项目里我主要做了 LangGraph 多阶段工作流、多轮 ReAct 自我修正、动态 RAG、SQL/结果/输出三道 Evaluator、FastAPI + WebSocket + React Thinking Panel，以及测试和评估体系。项目基于 Olist 电商数据集，覆盖 9 张业务表，100 条端到端评估综合得分 0.832，回答质量得分 0.908。

### Q2：你的项目一句话怎么介绍？

这是一个把“业务人员问问题、分析师写 SQL、解释结果”的流程封装成 Agent 工作流的系统。它不是简单调用一次大模型生成 SQL，而是通过 LangGraph 编排理解、推理、执行、反思、评估等阶段，让系统在 SQL 错误、结果为空、回答不完整时能够自动重试和修正。

### Q3：这个项目解决了什么实际问题？

传统 BI 查数需要业务人员和数据分析师反复沟通，业务问题要人工拆成指标、维度、时间范围、筛选条件，再写 SQL 查数和解释结果。这个项目希望让业务人员直接用自然语言提问，系统自动完成语义理解、查库和分析，同时把每一步过程可视化，避免 AI 黑盒。

### Q4：你的核心贡献是什么？

我的核心贡献有四块：

- 用 LangGraph 编排多阶段 Agent 工作流，并实现最多 5 轮的 ReAct 自我修正。
- 设计动态 RAG，在理解、推理、反思、分析阶段使用不同检索策略。
- 建立 SQL/结果/输出三道质量闸门，控制 SQL 安全、结果质量和回答幻觉。
- 实现 Thinking Panel、结构化日志、自动化测试和 100 题端到端评估，让系统可观察、可诊断、可评估。

## 2. AI 应用开发基础

### Q5：你理解的 AI 应用开发和普通后端开发有什么区别？

普通后端开发更关注确定性输入输出，比如接口参数、业务逻辑、数据库事务。AI 应用开发多了一个不确定的模型环节，模型可能输出格式错误、事实错误、SQL 错误，甚至回答超出数据范围。

所以 AI 应用开发除了接口和数据流，还要重点做 Prompt 约束、结构化输出、上下文管理、RAG、工具调用、结果校验、异常处理和评估体系。我的项目里用 Evaluator、RAG、反思修复和 Thinking Tracer 来约束模型输出。

### Q6：LLM 应用里为什么要做结构化输出？

因为后端系统需要稳定解析模型结果。如果让模型自由输出自然语言，很难可靠提取 SQL、意图、表名、字段映射等信息。

在项目里，`understand.j2` 要求模型返回 JSON，包括 `is_data_question`、`matched_tables`、`business_terms`、`needs_clarification` 等字段；`reason.j2` 也要求只返回 `{"sql": "SELECT ..."}`。这样后续节点可以按字段读取，而不是从自然语言里猜。

### Q7：Prompt Engineering 在你的项目里怎么体现？

我没有只写一句“请生成 SQL”，而是把 Prompt 按节点拆开：

- `understand.j2` 负责意图理解、非数据问题判断、表匹配和澄清问题。
- `reason.j2` 负责 DuckDB SQL 生成，并显式写入 JOIN 关系、日期规则、只读 SQL、LIMIT 等约束。
- `reflect.j2` 负责 SQL 错误修复。
- `analyze.j2` 负责结果解释和图表建议。
- `check.j2` 负责判断问题是否回答完整。

这样 Prompt 和 Agent 阶段一一对应，问题更容易定位和迭代。

### Q8：Context Engineering 和 Prompt Engineering 有什么区别？

Prompt Engineering 更偏“怎么问模型”，比如角色、输出格式、规则约束。Context Engineering 更偏“给模型什么信息”，比如历史对话、Schema、业务指标、上一轮 SQL、错误信息、RAG 检索结果。

在我的项目里，Context Engineering 体现在不同阶段给不同上下文：UNDERSTAND 给 Schema 和 Business Knowledge；REASON 给字段类型、JOIN 关系、业务口径和上一轮失败信息；REFLECT 给错误信息和失败 SQL；ANALYZE 给查询结果和分析知识。

## 3. LangGraph 与多轮 ReAct

### Q9：为什么使用 LangGraph，而不是自己写 if-else 流程？

这个项目有很多条件分支：非数据问题要拒答，信息不足要澄清，SQL 不安全要重写，SQL 执行失败要反思修复，结果为空要重新推理，回答不完整要继续下钻。如果用普通 if-else，流程会分散在各个函数里，后期很难维护。

LangGraph 的 `StateGraph` 和 `conditional_edges` 可以把流程编排集中在 `agent/graph.py`，节点逻辑和路由逻辑分离。每个节点只关心输入输出，整体流程更清晰。

### Q10：你的 Agent 工作流大概是怎样的？

主路径是：

`UNDERSTAND -> REASON -> SQL_EVAL -> ACT -> RESULT_EVAL -> ANALYZE -> CHECK -> OUTPUT_EVAL`

如果 `SQL_EVAL` 拒绝，会回到 `REASON` 重写 SQL；如果 `ACT` 执行报错，会进入 `REFLECT` 修复，再回到 `SQL_EVAL`；如果 `RESULT_EVAL` 发现空结果或质量不足，会回到 `REASON`；如果 `CHECK` 判断回答没有完成，会继续下一轮推理。

### Q11：什么是多轮 ReAct 自我修正？

我的理解是，Agent 不应该只“想一次、查一次、答一次”，而是要根据工具执行结果和质量检查结果继续调整策略。

在项目中，REASON 负责生成 SQL，ACT 执行 SQL，RESULT_EVAL 和 CHECK 对结果和回答质量做判断。如果 SQL 错、结果空或回答不完整，系统会回到推理或反思节点继续修正，最多 5 轮。这就是项目里的多轮 ReAct 自我修正。

### Q12：为什么不做多 Agent 架构？

当前项目的各阶段共享一个 `AgentState`，主要是一个数据分析任务链路。使用单 Agent + 多节点工作流已经能覆盖理解、推理、执行、反思、评估等流程。

多 Agent 更适合多个独立角色协作，比如 SQL Agent、Report Agent、Chart Agent、Reviewer Agent 各自独立决策。但多 Agent 会增加通信成本、状态同步复杂度和延迟。当前阶段我选择单 Agent 多节点，先保证链路稳定和可观测。

### Q13：AgentState 里保存了哪些状态？

`AgentState` 是整个 LangGraph 工作流传递的状态。它包括：

- 用户输入和会话信息：`session_id`、`user_query`、`messages`
- 语义理解结果：`intent`、`matched_tables`、`business_terms`
- SQL 链路：`generated_sql`、`sql_error`、`retry_count`
- 查询和分析结果：`query_result`、`result_summary`、`analysis_text`、`chart_config`
- 评估与异常：`evaluator_results`、`clarification_question`、`escalation_ticket`
- 多轮 ReAct：`react_round`、`accumulated_rounds`、`react_max_rounds`、`_check_complete`

这样每个节点都可以读取前面阶段的结果，并写入自己的输出。

## 4. RAG 与知识库

### Q14：为什么这个项目需要 RAG？

因为 LLM 本身不知道当前数据库有哪些表、字段、JOIN 关系和业务口径。如果直接让模型生成 SQL，很容易出现不存在的字段、错误 JOIN、错误指标定义。

RAG 的作用是把 Schema、业务指标、修复规则和分析方法检索出来，作为上下文喂给模型，让模型基于项目真实知识生成 SQL 和分析结果。

### Q15：你的动态 RAG 是怎么设计的？

我按 Agent 阶段设计了四类检索策略：

- UNDERSTAND：语义发现，检索相关表和业务术语。
- REASON：上下文补充，检索字段、JOIN 关系、指标口径。
- REFLECT：精确纠错，检索字段名、函数名、常见 SQL 错误修复规则。
- ANALYZE：领域知识，检索趋势、排行、分布、归因等分析方法。

代码里通过 `RAGRouter` 根据 `Stage` 分发到不同策略，而不是所有节点共用同一种检索方式。

### Q16：RAG 评估结果怎么说？

我做了离线 RAG 评估，整体 recall 是 83.5%，precision 是 63.2%。简历正文里我主要写 recall，因为这个系统更关注关键 Schema 和业务知识是否能被召回。UNDERSTAND 阶段 recall 是 89.3%，REASON 阶段 recall 是 92.8%，说明对理解和 SQL 生成最关键的两个阶段召回效果比较稳定。

如果面试官追问 precision，我会解释：为了保证 SQL 生成上下文足够，当前策略偏向召回更多候选，再由 Prompt 约束和 Evaluator 过滤噪声。

### Q17：为什么不只用向量检索？

因为 SQL 和 Schema 场景里有很多精确字段名、表名、函数名。纯向量检索适合语义相似，但对 `order_purchase_timestamp`、`DATE_FORMAT`、`TO_DAYS` 这类精确符号不一定稳定。

所以我在不同阶段结合向量、关键词和元数据权重。尤其 REFLECT 阶段更适合精确匹配错误字段或函数，而不是只靠语义相似。

### Q18：RAG 召回低时你怎么优化？

我会先看 missed knowledge，判断漏的是表、字段、业务指标还是修复规则。然后分情况处理：

- 如果漏 Schema，就补充表描述、字段别名和中英文映射。
- 如果漏业务指标，就补充业务口径，比如 GMV、客单价、支付占比。
- 如果漏 SQL 修复规则，就补充 Fix KB，例如 DuckDB 函数替换。
- 如果召回太多噪声，就调整 top-k、阈值和关键词/向量权重。

## 5. Text-to-SQL 与 SQL Agent

### Q19：Text-to-SQL 最大的难点是什么？

最大难点是模型生成 SQL 不稳定。它可能使用不存在的字段、错误 JOIN、数据库不支持的函数、忘记 LIMIT，或者根据用户模糊问题生成不符合业务口径的 SQL。

我的解决方式是：Schema RAG 提供上下文，Prompt 明确 JOIN 和 SQL 规则，SQL_EVAL 做执行前校验，ACT 捕获执行错误，REFLECT 做错误修复，RESULT_EVAL 检查结果质量。

### Q20：你如何保证生成的 SQL 安全？

第一，Prompt 里明确要求只生成 SELECT，并强制 LIMIT。  
第二，SQL_EVAL 使用规则引擎检查 SQL，不允许危险操作。  
第三，执行前会通过 Evaluator，只有通过后才交给 DW Connector 执行。  
第四，使用 DuckDB 开发环境，生产环境也可以通过只读账号和最小权限进一步控制。

### Q21：为什么一定要加 LIMIT？

LIMIT 有两个作用：一是防止误查大表导致内存和响应时间问题，二是让自然语言查询先返回可分析样本或聚合结果。尤其 Agent 生成 SQL 不一定总是最优，LIMIT 是一道低成本的保护。

在 `reason.j2` 里我明确写了 `ALWAYS include a LIMIT clause (max 1000)`。

### Q22：如果用户问“上个月销售额”，但数据只有 2016-2018，怎么办？

这个项目在 `understand.j2` 里明确处理相对时间。因为数据库只到 2018-10，如果用户说“上个月”“最近”“今年”等相对时间，系统会设置 `needs_clarification=true`，让用户指定具体历史时间，比如“数据库数据到 2018-10，你是指 2018 年 10 月吗？”

这比直接用当前日期生成 SQL 更安全。

### Q23：SQL 执行失败后怎么修？

执行失败后，`ACT` 会把错误写入 `sql_error`，路由到 `REFLECT`。REFLECT 会拿错误信息和失败 SQL 去检索 Fix KB / Schema KB，并应用确定性修复。

例如 DuckDB 不支持某些函数时，代码里会把 `DATE_FORMAT`、`TO_CHAR` 替换成 `STRFTIME`，把 `TO_DAYS(a) - TO_DAYS(b)` 改成 `DATEDIFF('day', b, a)`。修复后会回到 `SQL_EVAL` 再验证，而不是直接执行。

### Q24：为什么 REFLECT 不直接让 LLM 重新生成 SQL？

因为有些错误是确定性的，重新问 LLM 可能还会重复犯错。例如用户提到 MySQL 风格函数，模型可能一直生成 `DATE_FORMAT`，但 DuckDB 要用 `STRFTIME`。

所以 REFLECT 优先做确定性替换和规则修复，必要时才回退到 LLM 修复。这样比完全依赖模型重写更稳定。

## 6. Evaluator、测试与评估

### Q25：三道 Evaluator 分别做什么？

第一道是 SQL_EVAL，执行前检查 SQL 安全和语义质量，比如只读、LIMIT、危险关键字、LLM Judge 语义匹配。  
第二道是 RESULT_EVAL，执行后检查结果是否为空、是否和用户问题相关，必要时触发重新推理。  
第三道是 OUTPUT_EVAL，输出前检查回答质量，特别是回答中的数字是否来自原始结果集，降低幻觉结论风险。

### Q26：为什么需要 Evaluator？直接相信模型不行吗？

不行。LLM 的输出不稳定，尤其是 SQL 和数据分析场景，错误会直接影响结果可信度。Evaluator 相当于把模型输出放进工程约束里：能不能执行、结果有没有意义、回答是否忠实于数据。

没有 Evaluator，系统可能生成危险 SQL、空结果还强行解释，或者编造数据结论。

### Q27：100 条端到端评估怎么设计？

评估集覆盖了统计、排行、趋势、过滤、复杂 JOIN、归因、预测、边界问题和中英文问题。这样可以测试 Agent 在不同问题类型下的 SQL 生成、澄清、降级、拒答和回答质量。

当前报告里 100 条问题综合得分 0.832，SQL 得分 0.756，回答质量得分 0.908，平均响应 7.6 秒。

### Q28：为什么有 18 次澄清和 1 次升级，这是不是失败？

不完全是失败。对 Agent 来说，信息不足时澄清比胡乱回答更好。例如用户问“上个月”“利润率最高”但数据缺少成本字段，系统应该说明限制并反问，而不是编造结论。

升级代表系统识别到当前能力无法可靠回答，这也是异常处理的一部分。AI 应用不是所有问题都硬答，关键是知道什么时候答、什么时候问、什么时候拒绝。

### Q29：自动化测试覆盖了哪些？

项目有 91 条自动化测试，覆盖 Agent 节点、RAG Router、Prompt Manager、Evaluator 规则、上下文管理和 DW Connector 集成链路。单元测试保证确定性模块稳定，集成测试验证 Agent、数据仓库和 API 链路能协同工作。

### Q30：你怎么看 AI 应用的评估？

AI 应用评估不能只看“能不能回答”，要分层看：

- 检索层：RAG recall / precision。
- 工具层：SQL 是否安全、能否执行、结果是否有效。
- 回答层：回答是否忠实于数据、是否可读、是否满足用户问题。
- 系统层：平均耗时、重试次数、澄清/升级比例、错误分布。

我的项目也是按这些层次做评估，而不是只看模型主观效果。

## 7. 日志、异常与可观测性

### Q31：Thinking Panel 的价值是什么？

Thinking Panel 不是展示模型“内心想法”，而是展示 Agent 工程链路：每个节点的输入输出、耗时、Token、SQL、查询结果、Evaluator 状态和重试记录。

它的价值是让用户和开发者知道系统为什么这样回答。如果 SQL 错了、RAG 没召回、结果为空，都能看到失败发生在哪个节点。

### Q32：项目里怎么做日志和链路追踪？

项目有 `ThinkingTracer`，每个节点执行时调用 `record_step_start` 和 `record_step_end`，记录步骤名、状态、耗时、输出和错误；Evaluator 也会记录 gate、score 和 verdict。Tracer 可以通过 WebSocket 推给前端，也能用于调试和复盘。

此外还有 `MetricsCollector`，记录请求数、总耗时、Token、Evaluator 通过率、重试次数和错误级别。

### Q33：异常分级怎么讲？

我会按可恢复程度来讲：

- 可自愈异常：SQL 函数错误、字段名错误、空结果，可以通过 REFLECT 或重新推理修复。
- 需要澄清：时间范围不明确、指标定义不明确、用户问题缺少维度。
- 可降级：不能完整回答时，提供已有数据范围内的部分结果和限制说明。
- 需要升级：连续重试失败、数据源不可用、超出系统能力范围。

这比简单 try-except 更适合 Agent 系统。

### Q34：如果线上用户反馈回答错了，你怎么排查？

我会先根据 session_id 查 Thinking Trace，看 UNDERSTAND 是否匹配了正确表和业务术语；再看 REASON 生成的 SQL 和 SQL_EVAL 结果；然后看 ACT 返回的数据是否为空或异常；最后看 ANALYZE 和 OUTPUT_EVAL 是否把数据解释错。

如果是 RAG 漏召回，就补知识库或调权重；如果是 SQL 规则问题，就补 Prompt 或 Evaluator；如果是回答幻觉，就增强 OUTPUT_EVAL 和数据引用约束。

## 8. 架构与工程设计

### Q35：为什么要封装 LLM Provider？

不同模型接口、流式输出和 usage 字段可能不同。如果业务代码直接依赖某个模型 SDK，后续切换 DeepSeek、Qwen、GLM 会很麻烦。

项目里定义了 `BaseLLMProvider`，只暴露 `chat` 和 `stream` 两个接口。上层 Agent 节点只依赖抽象接口，不关心具体模型厂商。

### Q36：为什么要封装 DW Connector？

同理，开发环境用 DuckDB，但生产可能换 ClickHouse、StarRocks 或 PostgreSQL。通过 `BaseDWConnector` 抽象 `execute`、`describe`、`list_tables`、`health`，Agent 不需要关心底层数据库实现。

这也方便测试，可以用 mock connector 或 DuckDB fixture 做集成测试。

### Q37：为什么项目里选择 DuckDB？

DuckDB 适合本地分析型场景，部署简单，不需要单独起数据库服务，对 Olist 这种中等规模数据集足够。它支持 SQL 分析能力，方便快速验证 Text-to-SQL 和 Agent 工作流。

如果上生产，可以把 DW Connector 换成 ClickHouse 或 StarRocks。

### Q38：WebSocket 在这个项目里解决什么问题？

Agent 链路不是瞬时完成的，中间会经历 RAG、LLM、SQL 执行、评估、重试。HTTP 一次性返回会让用户等待黑盒结果。WebSocket 可以实时推送节点进度、SQL、结果和流式回答，让用户看到系统正在做什么。

### Q39：这个项目最大的技术难点是什么？

最大难点是把不确定的 LLM 输出变成可诊断、可恢复、可评估的工程系统。单次 SQL 生成很容易 demo，但要稳定处理字段错误、时间歧义、空结果、幻觉结论和多轮下钻，需要状态机、RAG、Evaluator、反思修复、日志和测试一起配合。

### Q40：如果继续迭代，你会做什么？

我会优先做四件事：

- 增强 REFLECT 阶段的函数和字段修复规则，提高修复召回。
- 引入 SQL 语义缓存，相似问题复用已验证 SQL，降低延迟和模型调用成本。
- 扩大 RAG 和端到端评估集，用更稳定的指标驱动迭代。
- 加入更细的数据权限和审计机制，支持企业 BI 场景。

## 9. 简历高频追问

### Q41：你简历里写“整体 recall 83.5%”，这个怎么算的？

这是离线 RAG 评估集的结果。每条评估样本包含用户问题、阶段、期望召回的知识点和实际检索结果。recall 计算的是期望知识点中被召回的比例。比如一个问题期望召回 orders 和 order_items 两个表，如果都召回就是 1.0，只召回一个就是 0.5。

### Q42：为什么回答质量得分 0.908，但 SQL 得分只有 0.756？

因为一些问题虽然 SQL 生成不完美，但系统会通过澄清、拒答、降级或自然语言解释给出合理回答。例如数据缺少成本字段时，系统不会强行计算利润率，而是说明无法直接回答。这会让回答质量高于 SQL 得分。

### Q43：简历里写“最多 5 轮下钻”，怎么控制不死循环？

`AgentState` 里有 `react_round` 和 `react_max_rounds`。CHECK 节点如果判断未完成，会回到 REASON；但如果达到最大轮数，就结束并输出当前最好结果或说明限制。SQL 执行错误和 SQL_EVAL 拒绝也有重试次数限制，避免无限重试。

### Q44：你怎么证明这个不是简单套壳？

套壳通常只是“前端输入 -> 调 LLM -> 返回文本”。我的项目有明确的工程链路：LangGraph 状态机、RAG Router、DW Connector、LLM Provider、SQL Evaluator、Result Evaluator、Output Evaluator、Thinking Tracer、自动化测试和端到端评估。

也就是说，LLM 只是其中一个组件，系统真正的价值在于流程编排、约束、工具调用、异常恢复和评估。

### Q45：你这个项目有哪些不足？

目前复杂分析、归因和预测类问题还有提升空间，100 题评估里 complex、why、edge 类别分数低于统计、排行和趋势类问题。REFLECT 阶段的 RAG recall 也低于 UNDERSTAND 和 REASON，说明错误修复知识库和精确匹配策略还需要继续补充。

我会把这些不足作为后续迭代方向，而不是只展示高分指标。

## 10. 反问面试官

### 可以反问的问题

- 贵团队现在 AI Agent 主要用于内部效率工具，还是面向外部用户的产品？
- 目前 Agent 系统更关注推理效果、延迟成本，还是稳定性和可观测性？
- 团队对 RAG / Tool Calling / Workflow Agent 的技术选型是偏 LangGraph 这类状态机，还是自研编排框架？
- 如果加入团队，实习生或校招生更可能参与 Prompt/RAG、后端接口、评估体系还是前端交互？

## 11. 面试前速记

- 项目定位：自然语言 BI 数据分析 Agent。
- 核心链路：UNDERSTAND -> REASON -> SQL_EVAL -> ACT -> RESULT_EVAL -> ANALYZE -> CHECK -> OUTPUT_EVAL。
- 核心卖点：LangGraph、多轮 ReAct、自修复、动态 RAG、三道 Evaluator、Thinking Panel、自动化测试和端到端评估。
- 指标：RAG recall 83.5%，UNDERSTAND 89.3%，REASON 92.8%；100 题综合 0.832，回答质量 0.908，平均 7.6s。
- 最大难点：让不稳定的 LLM 输出变成可诊断、可恢复、可评估的工程系统。
