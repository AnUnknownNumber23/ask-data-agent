# ReAct Agent 状态机图

```mermaid
flowchart TD
    subgraph Entry
        START([用户提问]) --> UNDERSTAND
    end

    subgraph "路由层 (5 个条件判断)"
        UNDERSTAND -->|匹配到表| REASON
        UNDERSTAND -->|反问澄清| CLARIFY
        UNDERSTAND -->|非数据问题| END1([END])
        CLARIFY --> END2([END])

        REASON --> SQL_EVAL

        SQL_EVAL -->|通过| ACT
        SQL_EVAL -->|拒绝| CHK_SQL{重试 ≥ 3?}
        CHK_SQL -->|否| REASON
        CHK_SQL -->|是| ESCALATE

        ACT -->|成功| RESULT_EVAL
        ACT -->|失败| CHK_ACT{重试 ≥ 3?}
        CHK_ACT -->|否| REFLECT
        CHK_ACT -->|是| ESCALATE

        REFLECT --> SQL_EVAL

        RESULT_EVAL -->|通过| ANALYZE
        RESULT_EVAL -->|0行| CHK_EMPTY{重试 ≥ 3?}
        CHK_EMPTY -->|否| REASON
        CHK_EMPTY -->|是| ANALYZE

        ESCALATE --> END3([END])
    end

    subgraph "核心循环 (最多5轮)"
        ANALYZE --> CHECK
        CHECK -->|完成| OUTPUT_EVAL
        CHECK -->|未完成| CHK_ROUND{轮次 ≥ 5?}
        CHK_ROUND -->|否| REASON
        CHK_ROUND -->|是| OUTPUT_EVAL
        OUTPUT_EVAL --> END4([END])
    end

    style UNDERSTAND fill:#4a90d9,color:#fff
    style REASON fill:#f5a623,color:#fff
    style SQL_EVAL fill:#7ed321,color:#fff
    style ACT fill:#f5a623,color:#fff
    style REFLECT fill:#bd10e0,color:#fff
    style RESULT_EVAL fill:#7ed321,color:#fff
    style ANALYZE fill:#4a90d9,color:#fff
    style CHECK fill:#50e3c2,color:#333
    style OUTPUT_EVAL fill:#7ed321,color:#fff
    style CLARIFY fill:#ff6b6b,color:#fff
    style ESCALATE fill:#ff6b6b,color:#fff
    style END1 fill:#999
    style END2 fill:#999
    style END3 fill:#999
    style END4 fill:#999
```

## 节点说明

| 节点 | 类型 | 职责 |
|------|------|------|
| UNDERSTAND | Agent | 意图解析 + 数据问题判断 + 相对时间反问 |
| REASON | Agent | 意图 → SQL |
| SQL_EVAL | Gate | SELECT/LIMIT/注入检测 |
| ACT | Exec | DuckDB 执行 SQL |
| REFLECT | Agent | 错误诊断 + 函数名直接替换 |
| RESULT_EVAL | Gate | 0 行检测 + 语义结果检查 |
| ANALYZE | Agent | 数据解读 + 图表生成 |
| CHECK | Agent | 问题回答完了吗？ |
| OUTPUT_EVAL | Gate | 幻觉检测（数值溯源） |
| CLARIFY | Agent | 反问澄清 |
| ESCALATE | Agent | 转人工 + 调整建议 |

## 三条自修正路径

| 错误类型 | 路由 | 上限 |
|---------|------|------|
| SQL 语法/安全检查不通过 | REASON 重写 | 3 次 → ESCALATE |
| SQL 执行失败（字段/函数不存在） | REFLECT 直接修复 | 3 次 → ESCALATE |
| 结果为空 | REASON 放宽条件 | 3 次 → ANALYZE |
| 分析不够深入 | CHECK → REASON 下钻 | 5 轮 → OUTPUT_EVAL |

## 条件路由分布

| 函数 | 从 | 到 | 条件 |
|------|----|----|------|
| `route_after_understand` | UNDERSTAND | CLARIFY / REASON / END | 有反问? / 非数据? |
| `route_after_sql_eval` | SQL_EVAL | ACT / REASON / ESCALATE | reject 且 <3 次? |
| `route_after_act` | ACT | RESULT_EVAL / REFLECT / ESCALATE | 有错误且 <3 次? |
| `route_after_result_eval` | RESULT_EVAL | ANALYZE / REASON | 0 行且 <3 次? |
| `route_after_check` | CHECK | OUTPUT_EVAL / REASON / ESCALATE | 完成? / 超 5 轮? |
