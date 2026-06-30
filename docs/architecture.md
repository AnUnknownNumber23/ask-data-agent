# 项目架构 · ER 图 · 数据流

## 一、项目架构

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (React)                          │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │     Chat Panel      │  │      Thinking Panel          │  │
│  │  · 对话流            │  │  · 每步 I/O 实时展示          │  │
│  │  · ECharts 图表      │  │  · SQL + 执行结果             │  │
│  │  · Markdown 报告     │  │  · 重试 / 评估 / Token        │  │
│  └──────────┬──────────┘  └──────────────┬───────────────┘  │
│             │         WebSocket 全双工     │                 │
├─────────────┼────────────────────────────┼─────────────────┤
│             ▼                            ▼                 │
│                  FastAPI 服务层                             │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐   │
│  │ POST     │  │ WS       │  │ POST /api/reports/      │   │
│  │ /api/chat│  │ /ws/chat │  │ generate               │   │
│  └────┬─────┘  └────┬─────┘  └───────────┬────────────┘   │
├───────┼─────────────┼────────────────────┼────────────────┤
│       ▼             ▼                    ▼                │
│            LangGraph Agent Runtime (11 节点)               │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                                                     │  │
│  │  UNDERSTAND ──→ REASON ──→ SQL_EVAL ──→ ACT         │  │
│  │      │             ↕           │          │          │  │
│  │   CLARIFY      REFLECT     (reject)   (error)       │  │
│  │      │                         │          │          │  │
│  │      ▼                         ▼          ▼          │  │
│  │     END                    REASON     REFLECT        │  │
│  │                                          │           │  │
│  │  ACT (success) → RESULT_EVAL → ANALYZE → CHECK       │  │
│  │                      │                      │        │  │
│  │                 (0 rows)              (done?)         │  │
│  │                      │                 │    │        │  │
│  │                      ▼              yes    no        │  │
│  │                   REASON              │    │         │  │
│  │                                       │    ▼         │  │
│  │                                  OUTPUT_EVAL  REASON │  │
│  │                                       │              │  │
│  │                                       ▼              │  │
│  │                                      END             │  │
│  └─────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│                    基础设施层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ LLM      │  │ DW       │  │ RAG      │  │ Memory   │  │
│  │ DeepSeek │  │ DuckDB   │  │ ChromaDB │  │ Session  │  │
│  │ /Qwen    │  │          │  │ 5 KB     │  │ Store    │  │
│  │ /GLM     │  │          │  │ 119 docs │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└───────────────────────────────────────────────────────────┘
```

## 二、ER 图

```
┌──────────────────────┐
│     customers        │  99,441 rows
│──────────────────────│
│ PK customer_id       │────┐
│    customer_unique_id│    │
│    customer_zip_code ─┐   │
│    customer_city      │   │
│    customer_state     │   │
└──────────────────────┘   │
        │ 1:N              │
        ▼                  │
┌──────────────────────┐   │    ┌──────────────────────┐
│       orders         │   │    │     geolocation      │
│──────────────────────│   │    │──────────────────────│
│ PK order_id          │─┐ │    │    zip_code_prefix ──┼── 关联 customers
│ FK customer_id       │ │ │    │    lat, lng          │     和 sellers
│    order_status      │ │ │    │    city, state       │
│    purchase_ts       │ │ │    └──────────────────────┘
│    approved_at       │ │ │
│    delivered_carrier │ │ │
│    delivered_customer│ │ │
│    estimated_delivery│ │ │
└──────────────────────┘ │ │
        │ 1:N             │ │
        ├─────────────────┘ │
        │ 1:N               │
        ▼                   ▼
┌──────────────────┐ ┌──────────────────┐
│   order_items    │ │  order_payments  │
│──────────────────│ │──────────────────│
│ FK order_id ─────┼─┤ FK order_id      │
│    order_item_id │ │    payment_seq   │
│ FK product_id ───┼┐│    payment_type  │
│ FK seller_id ────┼┼│    installments  │
│    price         │││    payment_value │
│    freight_value ││└──────────────────┘
│    shipping_date ││
└──────────────────┘│
        │            │
        │ N:1        │ N:1
        ▼            ▼
┌──────────────────┐ ┌──────────────────┐
│    products      │ │     sellers      │
│──────────────────│ │──────────────────│
│ PK product_id    │ │ PK seller_id     │
│    category_name─┼┐│    zip_code ─────┼── geolocation
│    weight_g      │││    city, state   │
│    length/height ││└──────────────────┘
│    /width_cm     ││
└──────────────────┘│
        │ N:1        │
        ▼            │
┌──────────────────────────┐
│  category_translation    │  71 rows
│──────────────────────────│
│ PK product_category_name │
│    category_name_english │
└──────────────────────────┘

┌──────────────────┐
│  order_reviews   │  99,224 rows
│──────────────────│
│ PK review_id     │
│ FK order_id ─────┼── orders
│    review_score  │
│    comment_title │
│    comment_msg   │
│    creation_date │
│    answer_ts     │
└──────────────────┘
```

**JOIN 路径：**

```
customers.customer_id = orders.customer_id
orders.order_id = order_items.order_id
orders.order_id = order_payments.order_id
orders.order_id = order_reviews.order_id
order_items.product_id = products.product_id
order_items.seller_id = sellers.seller_id
products.product_category_name = category_translation.product_category_name
customers.customer_zip_code_prefix ≈ geolocation.zip_code_prefix
sellers.seller_zip_code_prefix ≈ geolocation.zip_code_prefix
```

## 三、数据流

**请求处理全链路：**

```
用户输入 "为什么东南区毛利率跌了"
  │
  ▼
┌─ ① UNDERSTAND ────────────────────────────────────────┐
│  RAG 检索 (UNDERSTAND 策略)                           │
│    Schema KB: orders, order_items, customers          │
│    Business KB: 毛利率 = (price-freight)/price        │
│               : 东南区 = SP,RJ,MG,ES                  │
│  LLM 判断: is_data_question=true                      │
│  输出: matched_tables=[orders, order_items, customers]│
│        business_terms={毛利率:..., 东南区:...}         │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ② REASON ───────────────────────────────────────────┐
│  RAG 检索 (REASON 策略)                               │
│    Schema KB: 字段类型、JOIN 关系                     │
│    Business KB: 指标口径                              │
│  LLM 生成 SQL:                                        │
│    SELECT DATE_TRUNC('month', purchase_ts) AS month,  │
│           (SUM(price)-SUM(freight))/SUM(price)        │
│    FROM orders JOIN order_items ...                   │
│    WHERE customer_state IN ('SP','RJ','MG','ES')      │
│    GROUP BY month ORDER BY month LIMIT 1000           │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ③ SQL_EVAL ────────────────────────────────────────┐
│  规则引擎:                                            │
│    SELECT ✓  LIMIT ✓  no DROP/DELETE ✓                │
│  判决: pass                                           │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ④ ACT ─────────────────────────────────────────────┐
│  DuckDB 执行 SQL                                      │
│  返回: 23 rows × 2 cols                              │
│  耗时: 31ms                                          │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ⑤ RESULT_EVAL ─────────────────────────────────────┐
│  行数: 23 (正常)                                      │
│  判决: pass                                           │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ⑥ ANALYZE ─────────────────────────────────────────┐
│  RAG 检索 (ANALYZE 策略)                              │
│    Analytics KB: trend, ranking, margin frameworks   │
│  LLM 生成: 趋势解读 + 图表配置                         │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ⑦ CHECK ──────────────────────────────────────────┐
│  LLM 判断: 只分析了趋势，还没拆维度找根因              │
│  → not complete, needs_attribution=true              │
│  → next_step: "按品类拆毛利率，找出哪个品类跌最多"     │
└──────────────────────┬────────────────────────────────┘
                       │ (回 REASON, 第 2 轮)
                       ▼
┌─ ⑧ REASON (Round 2) ────────────────────────────────┐
│  收到 CHECK 指引: 按品类拆毛利率                       │
│  LLM 生成 SQL:                                        │
│    SELECT category,                                    │
│           (SUM(price)-SUM(freight))/SUM(price)        │
│    FROM ... GROUP BY category ORDER BY margin         │
└──────────────────────┬────────────────────────────────┘
                       ▼
               (SQL_EVAL → ACT → RESULT_EVAL → ANALYZE)
                       ▼
┌─ ⑨ CHECK (Round 2) ────────────────────────────────┐
│  LLM 判断: 已找到根因 (健康美容品类跌最多)             │
│  → complete=true                                      │
└──────────────────────┬────────────────────────────────┘
                       ▼
┌─ ⑩ OUTPUT_EVAL ────────────────────────────────────┐
│  数值溯源: 分析中的数字都在原始结果集中                │
│  判决: pass                                           │
└──────────────────────┬────────────────────────────────┘
                       ▼
              WebSocket 推送 → 前端渲染
```

**异常分支：**

```
ACT 报错 → REFLECT (RAG 诊断 + 直接修正) → SQL_EVAL → ACT
              │
              3 次全败 → ESCALATE → 用户收到调整建议

RESULT_EVAL 0 行 → REASON (放宽条件) → ... → 3 次仍空 → ANALYZE

CHECK not complete → REASON (下一轮) → ... → 5 轮上限 → OUTPUT_EVAL
```
