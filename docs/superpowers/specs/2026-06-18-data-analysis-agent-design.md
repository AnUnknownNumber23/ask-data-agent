# ask-data-agent — 完整设计文档

> 版本: v1.0  
> 日期: 2026-06-18  
> 项目名称: ask-data-agent  
> 数据集: Olist Brazilian E-commerce  
> 状态: 待审核

---

## 目录

1. [项目概述](#1-项目概述)
2. [数据集 Schema](#2-数据集-schema)
3. [系统架构](#3-系统架构)
4. [核心闭环: ReAct + 自修正](#4-核心闭环-react--自修正)
5. [异常处理体系](#5-异常处理体系)
6. [动态 RAG 检索策略](#6-动态-rag-检索策略)
7. [记忆与上下文管理](#7-记忆与上下文管理)
8. [Evaluator 评估体系](#8-evaluator-评估体系)
9. [报告系统](#9-报告系统)
10. [思考过程可视化 (Thinking Tracer)](#10-思考过程可视化-thinking-tracer)
11. [Prompt 模板管理](#11-prompt-模板管理)
12. [可插拔接口设计](#12-可插拔接口设计)
13. [测试策略](#13-测试策略)
14. [技术栈 & 项目结构](#14-技术栈--项目结构)
15. [部署](#15-部署)
16. [分阶段规划](#16-分阶段规划)
17. [设计原则](#17-设计原则)

---

## 1. 项目概述

### 1.1 定位

面向企业内部 BI 场景的**自助式数据分析 Agent**。业务人员用自然语言提问，Agent 自动理解意图、查询数据仓库、分析结果、生成回复或结构化报告。全过程在 Thinking Panel 中透明展示，根除 AI 黑盒。

### 1.2 核心能力

| 能力 | v1 | v2 |
|------|-----|-----|
| 描述性分析 (自然语言 → SQL → 图表) | ✅ | |
| 报告生成 — 模板驱动 (周报/月报/专题) | ✅ 手动触发 | 定时推送 |
| 报告生成 — AI 自主编排 | | ✅ |
| 归因分析 (维度下钻找原因) | 预留接口 | ✅ |
| 预测分析 | 预留接口 | ✅ |
| 指标预警 | 预留接口 | ✅ |

### 1.3 核心差异化

- **全过程透明**: Thinking Tracer 序列化每步 I/O，WebSocket 实时推送前端
- **自我纠错**: ReAct → 工具调用 → 异常捕获 → RAG 纠错 → 重试，形成闭环
- **三级质量门禁**: Evaluator 在 SQL/结果/输出三个节点把关，规则引擎 + LLM 双轨评估
- **动态 RAG**: 四阶段四策略，不同阶段切换不同检索模式
- **全可插拔**: LLM / DW / 向量库 / RAG 策略均适配器模式 + 配置驱动

---

## 2. 数据集 Schema

### 2.1 Olist Brazilian E-commerce

数据集来源: [Kaggle - Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

- **9 张表**，模拟真实电商数据仓库
- **时间跨度**: 2016-09 ~ 2018-10 (约 2 年)
- **总订单**: ~10 万
- **总客户**: ~10 万
- **数据量**: ~12 万行订单明细，适合单机 DuckDB 开发，也支持迁移到 ClickHouse/StarRocks

### 2.2 ER 图

```
┌──────────────────┐
│    customers     │  99,441 rows
│──────────────────│
│ PK customer_id   │────┐
│    customer_zip  │    │
│    customer_city │    │
│    customer_state│    │
└──────────────────┘    │
                        │  1:N
                        v
┌──────────────────┐        ┌──────────────────────┐
│     orders       │        │     geolocation       │  1,000,163 rows
│──────────────────│        │──────────────────────│
│ PK order_id      │──┐     │    zip_code_prefix    │──┐ 关联 customers 和
│ FK customer_id   │  │     │    lat, lng           │  │ sellers 的地理位置
│    order_status  │  │     │    city, state        │  │
│    purchase_ts   │  │     └──────────────────────┘  │
│    approved_at   │  │                               │
│    delivered_*   │  │                               │
└──────────────────┘  │                               │
        │              │                               │
        │ 1:N          │ 1:N                           │
        v              v                               │
┌──────────────────┐ ┌──────────────────┐             │
│   order_items    │ │ order_payments   │             │
│──────────────────│ │──────────────────│             │
│ FK order_id ─────┼─┤ FK order_id      │             │
│    order_item_id │ │    payment_seq   │             │
│ FK product_id ───┼─┐│    payment_type  │             │
│ FK seller_id ────┼─┼│    installments │             │
│    price         │ ││    payment_value │             │
│    freight_value │ │└──────────────────┘             │
│    shipping_date │ │                                 │
└──────────────────┘ │                                 │
        │             │                                 │
        │ N:1         │ N:1                             │
        v             v                                 │
┌──────────────────┐ ┌──────────────────┐             │
│    products      │ │    sellers       │             │
│──────────────────│ │──────────────────│             │
│ PK product_id    │ │ PK seller_id     │             │
│    category_name─┼─┐│    zip_code ─────┼─────────────┘
│    weight_g      │ ││    city, state  │
│    length/height │ │└──────────────────┘
│    /width_cm     │ │
│    photos_qty    │ │
└──────────────────┘ │
        │             │
        │ N:1         │
        v             │
┌──────────────────────────┐
│ category_translation     │  71 rows
│──────────────────────────│
│ PK product_category_name │
│    category_name_english │
└──────────────────────────┘

        ┌──────────────────┐
        │ order_reviews    │  99,224 rows
        │──────────────────│
        │ PK review_id     │
        │ FK order_id ─────┼── 关联 orders
        │    review_score  │
        │    comment_title │
        │    comment_msg   │
        │    creation_date │
        │    answer_ts     │
        └──────────────────┘
```

### 2.3 详细字段

#### customers (99,441 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| customer_id | VARCHAR | 主键, 订单级唯一标识 |
| customer_unique_id | VARCHAR | 客户唯一标识 (一个客户可有多个 customer_id) |
| customer_zip_code_prefix | VARCHAR | 邮编前缀 (关联 geolocation) |
| customer_city | VARCHAR | 城市 (巴西葡萄牙语) |
| customer_state | VARCHAR | 州 (SP=圣保罗, RJ=里约, ...) |

#### orders (99,441 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | VARCHAR | 主键 |
| customer_id | VARCHAR | FK → customers |
| order_status | VARCHAR | delivered / shipped / canceled / unavailable / ... |
| order_purchase_timestamp | TIMESTAMP | 下单时间 |
| order_approved_at | TIMESTAMP | 审核时间 |
| order_delivered_carrier_date | TIMESTAMP | 交运时间 |
| order_delivered_customer_date | TIMESTAMP | 妥投时间 |
| order_estimated_delivery_date | TIMESTAMP | 预计交付时间 |

#### order_items (112,650 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | VARCHAR | FK → orders |
| order_item_id | BIGINT | 订单内商品序号 |
| product_id | VARCHAR | FK → products |
| seller_id | VARCHAR | FK → sellers |
| shipping_limit_date | TIMESTAMP | 发货截止时间 |
| price | DOUBLE | 商品单价 |
| freight_value | DOUBLE | 运费 |

#### order_payments (103,886 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | VARCHAR | FK → orders |
| payment_sequential | BIGINT | 支付序号 (一个订单可多笔支付) |
| payment_type | VARCHAR | credit_card / boleto / voucher / debit_card |
| payment_installments | BIGINT | 分期数 |
| payment_value | DOUBLE | 支付金额 |

#### order_reviews (99,224 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| review_id | VARCHAR | 主键 |
| order_id | VARCHAR | FK → orders |
| review_score | BIGINT | 评分 (1-5) |
| review_comment_title | VARCHAR | 评论标题 (可 NULL) |
| review_comment_message | VARCHAR | 评论内容 (可 NULL) |
| review_creation_date | TIMESTAMP | 评论时间 |
| review_answer_timestamp | TIMESTAMP | 卖家回复时间 |

#### products (32,951 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | VARCHAR | 主键 |
| product_category_name | VARCHAR | 品类名 (葡萄牙语, FK → category_translation) |
| product_name_lenght | BIGINT | 商品名长度 |
| product_description_lenght | BIGINT | 描述长度 |
| product_photos_qty | BIGINT | 图片数量 |
| product_weight_g | BIGINT | 重量 (克) |
| product_length_cm | BIGINT | 长 (cm) |
| product_height_cm | BIGINT | 高 (cm) |
| product_width_cm | BIGINT | 宽 (cm) |

#### sellers (3,095 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| seller_id | VARCHAR | 主键 |
| seller_zip_code_prefix | VARCHAR | 邮编前缀 |
| seller_city | VARCHAR | 城市 |
| seller_state | VARCHAR | 州 |

#### geolocation (1,000,163 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| geolocation_zip_code_prefix | VARCHAR | 邮编前缀 (一个前缀可对多组经纬度) |
| geolocation_lat | DOUBLE | 纬度 |
| geolocation_lng | DOUBLE | 经度 |
| geolocation_city | VARCHAR | 城市 |
| geolocation_state | VARCHAR | 州 |

#### category_translation (71 rows)

| 字段 | 类型 | 说明 |
|------|------|------|
| product_category_name | VARCHAR | 主键, 葡萄牙语品类名 |
| product_category_name_english | VARCHAR | 英语品类名 |

### 2.4 典型分析场景映射

| 用户自然语言问题 | Agent 路径 | 涉及表 |
|------------------|-----------|--------|
| "上个月东南区 GMV 跌了,为什么?" | UNDERSTAND → RAG → SQL → 结果 → REPLY | orders, order_items, customers, geolocation |
| "哪个品类评分最高?" | 同上 | products, order_reviews, category_translation |
| "信用卡支付占比趋势?" | 同上 | order_payments, orders |
| "生成东南区 2017 年双十一分析报告" | 同前 → PLAN_REPORT → 并行取数 → 组装 | 全部 |
| "哪个城市订单最多?" | 同上 | orders, customers |
| "客单价变化趋势?" | 同上 | order_items, orders |
| "卖家集中度怎么样?" | 同上 | order_items, sellers |

---

## 3. 系统架构

### 3.1 六层架构总图

```
┌──────────────────────────────────────────────────────────────────────┐
│                          接入层 — Web UI (React)                      │
│                                                                      │
│  ┌─────────────────────────┐  ┌──────────────────────────────────┐  │
│  │       Chat Panel        │  │     Thinking Process Panel        │  │
│  │                         │  │                                   │  │
│  │  · 对话流 (流式渲染)    │  │  · ReAct 推理步骤节点图            │  │
│  │  · 图表 (ECharts)       │  │  · SQL + 执行结果                 │  │
│  │  · 表格 (可排序/筛选)   │  │  · 异常 + 重试记录                │  │
│  │  · 报告 (多章节渲染)    │  │  · RAG 检索摘要                   │  │
│  │  · 文本可内联编辑       │  │  · Evaluator 门禁状态             │  │
│  │                         │  │  · 每步耗时 + Token 用量          │  │
│  └────────────┬────────────┘  └───────────────┬──────────────────┘  │
│               │                               │                      │
│               └───────────────┬───────────────┘                      │
│                               │ WebSocket (全双工流式)                │
├───────────────────────────────┼──────────────────────────────────────┤
│                          服务层 — FastAPI                            │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 鉴权     │ │ Session  │ │ 限流     │ │ WS       │ │ 报告管理   │ │
│  │ JWT/SSO  │ │ 管理     │ │ 并发控制 │ │ Manager  │ │ CRUD/归档  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                    智能层 — LangGraph Agent Runtime                   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  State Machine (详见 §4)                                       │ │
│  │  UNDERSTAND → REASON → [SQL Eval ☐] → ACT → [Result Eval ☐]   │ │
│  │     ↕ REFLECT (纠错)  ↕ CLARIFY (L1)  ↕ DEGRADE (L2)  ↕ ESCALATE (L3) │
│  │     → ANALYZE → REPLY / PLAN_REPORT → [Output Eval ☐] → 推送   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌───────────────────┐  ┌──────────────────────────────────┐        │
│  │  Memory Manager   │  │      Prompt Manager               │        │
│  │  · 工作记忆(State)│  │  · 模板加载/渲染/版本管理         │        │
│  │  · 会话记忆(Redis)│  │  · understand/reason/reflect/     │        │
│  │  · 长期知识(向量库)│  │    analyze/clarify/degrade/        │        │
│  │  · 上下文窗口管理  │  │    report_*/evaluator_judge.j2    │        │
│  └───────────────────┘  └──────────────────────────────────┘        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ═══════════════════ 横切关注点: monitoring ════════════════════════ │
│  ┌───────────────────┐  ┌──────────────────────────────────┐        │
│  │   Thinking Tracer │  │   Metrics Collector              │        │
│  │   · 每步 I/O 序列化│  │   · Token 用量统计               │        │
│  │   · WS 实时推送   │  │   · 响应时间分布                 │        │
│  │   · 全链路可追溯  │  │   · Evaluator 通过率              │        │
│  └───────────────────┘  └──────────────────────────────────┘        │
│  ════════════════════════════════════════════════════════════════════ │
│                                                                      │
│                   能力层 — 工具 · RAG · Evaluator                    │
│                                                                      │
│  ┌────────────────┐ ┌──────────────────┐ ┌──────────────────────┐   │
│  │  DW Connector  │ │ Dynamic RAG      │ │     Evaluator        │   │
│  │  (可插拔)      │ │ Router           │ │                      │   │
│  │                │ │                  │ │ Gate 1: SQL 评估     │   │
│  │  · DuckDB(开发)│ │ 4阶段4策略:      │ │   · Rule Engine      │   │
│  │  · ClickHouse  │ │ · UNDERSTAND     │ │   · LLM Judge        │   │
│  │  · StarRocks   │ │   语义发现       │ │                      │   │
│  │                │ │ · REASON         │ │ Gate 2: 结果评估     │   │
│  │  统一接口:     │ │   上下文补充     │ │ Gate 3: 输出评估     │   │
│  │  · execute()   │ │ · REFLECT        │ │                      │   │
│  │  · describe()  │ │   精确纠错       │ │ 阈值: ≥0.8通过       │   │
│  │  · health()    │ │ · ANALYZE        │ │      0.6~0.8警告     │   │
│  └────────────────┘ │   领域知识       │ │      <0.6拒绝        │   │
│                     │                  │ └──────────────────────┘   │
│                     │ 混合检索引擎:   │                             │
│                     │ · 向量检索      │                             │
│                     │ · 关键词(BM25)  │                             │
│                     │ · 元数据过滤    │                             │
│                     │ · Rerank        │                             │
│                     └──────────────────┘                             │
├──────────────────────────────────────────────────────────────────────┤
│                           数据层                                     │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Schema KB│ │Business KB│ │Analytics │ │  Fix KB  │ │ Eval KB  │  │
│  │          │ │          │ │    KB    │ │          │ │          │  │
│  │ · 表结构 │ │ · 指标定义│ │ · 分析框架│ │ · 错误→  │ │ · 评估记录│  │
│  │ · 字段   │ │ · 术语映射│ │ · 可视化  │ │   修正   │ │ · 质量统计│  │
│  │ · 索引   │ │ · 常见SQL │ │ · 历史案例│ │ · 同义词 │ │          │  │
│  │ · 关系   │ │          │ │          │ │ · 别名   │ │          │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                      │
│  ┌──────────┐ ┌──────────────────┐ ┌────────────────────────┐       │
│  │  Redis   │ │ ChromaDB/Milvus  │ │   PostgreSQL            │       │
│  │  会话缓存│ │ 向量数据库       │ │   报告/用户/配置       │       │
│  └──────────┘ └──────────────────┘ └────────────────────────┘       │
├──────────────────────────────────────────────────────────────────────┤
│                         基础设施层                                   │
│                                                                      │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │
│  │ LLM        │ │ SQL      │ │ 报告     │ │ 监控 & 日志          │  │
│  │ Provider   │ │ 执行引擎 │ │ 引擎     │ │                      │  │
│  │ (可插拔)   │ │          │ │          │ │ · Prometheus         │  │
│  │            │ │ · DW连接 │ │ · Markdown│ │ · OpenTelemetry      │  │
│  │ · DeepSeek │ │ · 防注入 │ │ · ECharts │ │ · Eval 质量看板      │  │
│  │ · Qwen     │ │ · 超时控制│ │ · PDF导出 │ │                      │  │
│  │ · GLM      │ │ · 行数限制│ │ · Excel   │ │                      │  │
│  └────────────┘ └──────────┘ └──────────┘ └──────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │     Docker Compose (纯内网)                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心闭环: ReAct + 自修正

### 4.1 状态机

```
用户自然语言问题
        │
        v
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  ① UNDERSTAND ─── RAG 语义发现策略                            │
  │       │                                                      │
  │       ├── 匹配到表 ──→ ② REASON ─── RAG 上下文补充            │
  │       │                      │                               │
  │       │                      v                               │
  │       │               🛡 Gate 1: SQL Evaluator                │
  │       │                      │                               │
  │       │                 ┌────┴────┐                           │
  │       │               通过      拒绝 → 返回 REASON 重写       │
  │       │                 │                                    │
  │       │                 v                                    │
  │       │              ③ ACT (执行 SQL)                         │
  │       │                 │                                    │
  │       │            ┌────┴────────────────┐                   │
  │       │          成功                  失败                    │
  │       │            │                    │                    │
  │       │            v                    v                    │
  │       │     🛡 Gate 2: Result Eval  ④ REFLECT                 │
  │       │            │               · 错误诊断                 │
  │       │       ┌────┴────┐          · RAG 精确纠错策略          │
  │       │     通过    需补充│          · 修正 SQL                │
  │       │       │       │              │                        │
  │       │       │       └→ REASON     │                        │
  │       │       │                 ┌────┴──────┐                │
  │       │       │              修正成功    3次全败               │
  │       │       │               │            │                  │
  │       │       │           REASON(重试)  ESCALATE (L3)          │
  │       │       │               │         转人工                │
  │       │       │               │                               │
  │       │       v               v                               │
  │       │  ┌────────────────────────────────┐                   │
  │       │  │       ⑤ ANALYZE                │                   │
  │       │  │  分析结果 + RAG 领域知识         │                   │
  │       │  └───────────┬────────────────────┘                   │
  │       │              │                                        │
  │       │     ┌────────┴────────┐                               │
  │       │     v                 v                               │
  │       │  REPLY (对话)    PLAN_REPORT                           │
  │       │     │                 │                               │
  │       │     │            · 并行取数 (最大3并发)                 │
  │       │     │            · 逐章组装                            │
  │       │     │            · 整体润色                            │
  │       │     │                 │                               │
  │       │     └────────┬────────┘                               │
  │       │              │                                        │
  │       │              v                                        │
  │       │       🛡 Gate 3: Output Evaluator                     │
  │       │              │                                        │
  │       │         ┌────┴────┐                                   │
  │       │       通过     需修正 → 局部重写                       │
  │       │         │                                             │
  │       │         v                                             │
  │       │     ⑥ 推送用户                                        │
  │       │                                                      │
  │       └── 无匹配 ──→ CLARIFY 反问澄清 (L1) → 等用户输入        │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

### 4.2 自修正示例 (基于 Olist)

```
用户问: "上个月东南区毛利率为什么跌了?"

① UNDERSTAND (RAG 语义发现)
   从 Schema KB 匹配: orders, order_items, customers, geolocation
   从 Business KB 匹配: "毛利率" = (price - freight_value) / price
                      "东南区" = customer_state IN ('SP','RJ','MG','ES')

② REASON (RAG 上下文补充)
   拉取: 4 张表的 JOIN 关系、字段类型、分区键
   生成 SQL:
   SELECT DATE_TRUNC('month', o.order_purchase_timestamp) as m,
          c.customer_state,
          (SUM(oi.price) - SUM(oi.freight_value)) / SUM(oi.price) as margin
   FROM orders o
   JOIN order_items oi ON o.order_id = oi.order_id
   JOIN customers c ON o.customer_id = c.customer_id
   WHERE c.customer_state IN ('SP','RJ','MG','ES')
     AND o.order_purchase_timestamp >= '2018-03-01'
   GROUP BY m, c.customer_state
   LIMIT 1000

🛡 Gate 1 → 通过

③ ACT → 执行 → 返回 23 行

🛡 Gate 2 → 通过

④ ANALYZE (RAG 领域知识)
   匹配分析框架: "毛利率下降" → 拆维度下钻 (州/品类/卖家)
   生成回复: 文字解读 + 趋势折线图 + 州维度柱状图

🛡 Gate 3 → 通过 → 推送

--- 如果有错 ---
REFLECT 阶段:
  · SQL 报 "column not found: order_date"
  · RAG 精确纠错: 关闭向量, 关键词查 Schema KB → order_purchase_timestamp
  · 修正 SQL, 重试
  · 3次仍败 → ESCALATE
```

---

## 5. 异常处理体系

### 5.1 四级分级

| 级别 | 定义 | 策略 | 示例 | 前端标识 |
|------|------|------|------|----------|
| **L0 可自愈** | Agent 能自己修复 | RAG 纠错 → 自动重试 ≤3 次 | SQL 语法错、字段名错、结果为空放宽条件 | 🔄 |
| **L1 需澄清** | 需用户补充信息 | 反问用户，暂停等回复 | 表不明确、多表候选、问题模糊 | ⚠️ |
| **L2 可降级** | 无法完美但有备选 | 给部分/抽样/相邻数据 + 说明 | 当月无数据展示相邻时段、数据量大抽样 | ⚠️ |
| **L3 需介入** | 超出能力范围 | 打包上下文 → 工单/通知 | 3次重试全败、DW 不可用、权限不足 | 🔴 |

### 5.2 退避重试策略

```
重试次数       重试间隔        行为
─────────────────────────────────────────
第 1 次        0s (立即)      修正 SQL 直接重试
第 2 次        2s             换个角度重写 SQL
第 3 次        5s             放宽条件/降级策略
第 4 次        ─              不重试，转 L3 人工
```

---

## 6. 动态 RAG 检索策略

### 6.1 策略矩阵

| 阶段 | 策略名称 | 向量权重 | 关键词权重 | 元数据权重 | Top-K | 阈值 | 知识库 |
|------|----------|----------|------------|------------|-------|------|--------|
| UNDERSTAND | 语义发现 | 0.6 | 0.3 | 0.1 | 5 | 0.65 | Schema + Business |
| REASON | 上下文补充 | 0.3 | 0.2 | 0.5 | 8 | 0.5 | Schema + Business |
| REFLECT | **精确纠错** | **0.0** | 0.6 | 0.4 | 3 | 无 | Schema + Fix |
| ANALYZE | 领域知识 | 0.7 | 0 | 0.3 | 3 | 0.7 | Analytics |

---

## 7. 记忆与上下文管理

### 7.1 四层记忆

| 记忆层 | 存储 | 内容 | 生命周期 |
|--------|------|------|----------|
| **工作记忆** | LangGraph State | 当前问题全链: SQL/结果/推理链/评估/修正记录 | 单次请求 |
| **会话记忆** | Redis | 本轮对话历史、多轮上下文、修正记录累积 | 会话过期清 |
| **长期知识** | ChromaDB (向量库) | 表结构、业务口径、分析模式、纠错知识 | 持久化 |
| **上下文窗口** | Token 计算器 | 动态摘要压缩、大结果集截断、历史对话合并 | 每轮评估 |

---

## 8. Evaluator 评估体系

### 8.1 三道门禁

```
Gate 1: SQL Evaluator (执行前)
  ├─ Rule Engine (毫秒级, 零 token)
  │   · 必须是 SELECT
  │   · 禁止 DROP/DELETE/INSERT/UPDATE/TRUNCATE
  │   · 必须有 LIMIT (最大 10000)
  │   · 分区键/索引是否命中
  │   · JOIN 类型合理
  │
  └─ LLM Judge (小模型, 秒级)
      · SQL 语义 vs 用户意图 匹配度
      · 打分 0-1
      · ≥0.8 通过 | 0.6~0.8 警告 | <0.6 拒绝

Gate 2: Result Evaluator (执行后)
  ├─ Rule Engine
  │   · 行数 = 0? → 触发 REFLECT 放宽条件
  │   · 行数 = LIMIT 上限? → 警告可能不全
  │   · 空值率 > 30%? → 警告
  │   · 数值列统计 (min/max/avg/std)
  │
  └─ LLM Judge
      · 结果 vs 意图 相关性
      · 是否需补充查询
      · 打分 0-1

Gate 3: Output Evaluator (推送前)
  ├─ Rule Engine
  │   · 硬校验: 结论中数值是否在原始结果集中存在
  │   · 图表配置有效性
  │
  └─ LLM Judge
      · 结论与数据一致性 (幻觉检测)
      · 可读性/专业性
      · 报告章节逻辑连贯性
      · 打分 0-1
```

---

## 9. 报告系统

### 9.1 报告流程

```
用户触发 (手动: "生成报告"/按钮)
        │
        v
   PLAN_REPORT ── Agent 规划报告大纲 + 数据查询计划
        │
        v
   并行取数 ── 最大 3 并发，每个查询走完整 ReAct + Eval
        │
        v
   逐章组装 ── 每章: 数据 → 图表配置 → AI 解读文本
        │
        v
   整体润色 ── 检查章节间一致性、去重、生成摘要 + 行动建议
        │
        v
 🛡 Output Evaluator
        │
        v
   渲染推送 ── → JSON → 前端
        │
   ┌────┼────┐
   v    v    v
在线交互  PDF  Excel
```

---

## 10. 思考过程可视化 (Thinking Tracer)

Tracer 是横切关注点 (Cross-cutting Concern)，独立于状态机，嵌入每个节点：

```
monitoring/                    # 横切关注点模块
├── tracer.py                  # 思考过程追踪器
└── metrics.py                 # Token/耗时/质量指标收集器

每个节点执行:
  tracer.record_step_start(step_name)
  → 节点逻辑
  → tracer.record_step_end(output, duration, tokens)
  → tracer.push_to_websocket()
```

---

## 11. Prompt 模板管理

### 11.1 目录结构

```
prompts/
├── manager.py                  # 模板加载/渲染/版本管理
├── templates/
│   ├── understand.j2           # 意图解析 + RAG 语义发现
│   ├── reason.j2               # SQL 推理 + 上下文补充
│   ├── reflect.j2              # 错误反思 + 精确纠错
│   ├── analyze.j2              # 分析解读 + 领域知识
│   ├── clarify.j2              # L1 反问澄清
│   ├── degrade.j2              # L2 降级输出
│   ├── report_plan.j2          # 报告规划
│   ├── report_assemble.j2      # 报告逐章组装
│   └── evaluator_judge.j2      # LLM Judge 评分 Prompt
└── config/
    └── prompt_config.yaml      # 模板元信息 (版本/描述/变量定义)
```

---

## 12. 可插拔接口设计

### 12.1 LLM Provider

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> ChatResponse: ...
    @abstractmethod
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[Token]: ...

class DeepSeekProvider(BaseLLMProvider): ...
class QwenProvider(BaseLLMProvider): ...
class GLMProvider(BaseLLMProvider): ...
```

### 12.2 DW Connector

```python
class BaseDWConnector(ABC):
    @abstractmethod
    async def execute(self, sql: str) -> QueryResult: ...
    @abstractmethod
    async def describe(self, table: str) -> TableSchema: ...
    @abstractmethod
    async def health(self) -> bool: ...

class DuckDBConnector(BaseDWConnector): ...       # 开发环境
class ClickHouseConnector(BaseDWConnector): ...    # 生产环境
class StarRocksConnector(BaseDWConnector): ...
```

### 12.3 RAG Strategy

```python
class RAGRouter:
    def retrieve(self, stage: Stage, query: Query, context: Context) -> RAGResult:
        strategy = self._get_strategy(stage)  # 策略工厂按 Stage 分发
        return strategy.execute(query, context)
```

---

## 13. 测试策略

### 13.1 测试金字塔

```
           ┌────────────┐
           │   E2E (v2) │  CI 全链路: 用户问题 → Agent → DW → 回复
           ├────────────┤
           │ Integration│  Agent 状态机 + DW Connector + FastAPI
           ├────────────┤
           │   Unit     │  规则引擎 / RAG Router / Prompt Manager
           └────────────┘  上下文窗口 / 各节点 Pure Functions
```

---

## 14. 技术栈 & 项目结构

### 14.1 技术选型

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | React + TypeScript | Chat + Thinking 双面板 |
| 前端图表 | ECharts | 可交互图表 |
| 前端 WS | reconnecting-websocket | WebSocket 流式通信 |
| 后端 | FastAPI (Python 3.11+) | HTTP + WebSocket |
| Agent 框架 | LangGraph | 状态机编排 |
| SQL 生成 | 原生 Python + Prompt 模板 | 核心逻辑自研 |
| LLM 调用 | 原生 httpx + SSE | 流式调用 |
| LLM | DeepSeek / Qwen / GLM | 可插拔适配器 |
| 向量库 (dev) | ChromaDB | RAG 知识库 |
| 向量库 (prod) | Milvus | 分布式向量库 |
| 缓存 | Redis | 会话记忆 |
| 业务库 | PostgreSQL | 报告/用户/配置 |
| DW (dev) | DuckDB | 单机文件, 零依赖 |
| DW (prod) | ClickHouse / StarRocks | 可插拔切换 |
| 监控 | Prometheus + OpenTelemetry | 指标 + 链路追踪 |
| 部署 | Docker Compose | 纯内网 |

### 14.2 完整目录结构

```
ask-data-agent/
├── agent/                      # Agent 核心
│   ├── graph.py                # LangGraph 状态机定义
│   ├── state.py                # State Schema
│   └── nodes/                  # 各节点实现
│       ├── understand.py
│       ├── reason.py
│       ├── act.py
│       ├── reflect.py
│       ├── analyze.py
│       ├── clarify.py
│       ├── degrade.py
│       └── escalate.py
│
├── monitoring/                 # 横切关注点
│   ├── tracer.py
│   └── metrics.py
│
├── rag/                        # 动态 RAG
│   ├── router.py
│   ├── strategies/
│   │   ├── understand.py
│   │   ├── reason.py
│   │   ├── reflect.py
│   │   └── analyze.py
│   └── knowledge/
│       ├── schema_kb.py
│       ├── business_kb.py
│       └── fix_kb.py
│
├── evaluator/                  # 质量门禁
│   ├── gates/
│   │   ├── sql_eval.py
│   │   ├── result_eval.py
│   │   └── output_eval.py
│   └── rules.py
│
├── prompts/                    # Prompt 模板管理
│   ├── manager.py
│   ├── templates/
│   └── config/
│       └── prompt_config.yaml
│
├── connectors/                 # 可插拔连接器
│   ├── llm/
│   │   ├── base.py
│   │   ├── deepseek.py
│   │   ├── qwen.py
│   │   └── glm.py
│   └── dw/
│       ├── base.py
│       ├── duckdb.py
│       └── ...
│
├── memory/                     # 记忆管理
│   └── context.py
│
├── report/                     # 报告引擎
│   ├── planner.py
│   ├── assembler.py
│   └── renderer.py
│
├── api/                        # FastAPI
│   ├── main.py
│   ├── routes/
│   │   ├── chat.py
│   │   └── report.py
│   └── ws.py
│
├── web/                        # React 前端
│   └── src/
│       ├── panels/
│       └── hooks/
│
├── tests/                      # 测试
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── data/
│   └── olist.duckdb
│
├── config/
│   └── config.yaml
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-18-data-analysis-agent-design.md
```

---

## 15. 部署

### 15.1 Docker Compose (纯内网)

```yaml
services:
  nginx:      # 反向代理 (80)
  frontend:   # React (5173)
  backend:    # FastAPI (8000)
  redis:      # 会话缓存 (6379)
  chromadb:   # 向量库 (8001)
  postgres:   # 业务库 (5432)
  llm-proxy:  # LLM 网关 (8080, 可选)
```

---

## 16. 分阶段规划

### v1 (MVP — 当前)

- ReAct 状态机 + 8 节点
- 四阶段动态 RAG + 3 个知识库
- 三道 Evaluator 门禁
- 四层记忆管理
- 9 个 Prompt 模板 + 版本管理
- 模板驱动报告 (周报/月报/专题)
- Chat Panel + Thinking Panel
- DuckDB + Olist 数据集
- Docker Compose 纯内网部署
- 单元测试 + 集成测试

### v2

- 归因分析、预测、预警
- 定时报告 + Cron 推送
- AI 自主编排报告
- ChromaDB → Milvus 升级
- 多租户 + 列级数据权限
- K8s 部署

---

## 17. 设计原则

| 原则 | 说明 |
|------|------|
| **全链路可追踪** | Tracer 每步 I/O → WebSocket → 前端, 彻底去黑盒 |
| **自我纠错闭环** | ReAct + RAG 精确纠错 + Evaluator 三级门禁 |
| **失败安全** | L0→L3 分级异常, 永不死循环, 永不静默失败 |
| **Prompt 即代码** | 全部 Prompt 模板化 + 版本管理, 与业务逻辑解耦 |
| **可插拔优先** | LLM / DW / 向量库 / RAG 策略 全部适配器 + 配置驱动 |
| **YAGNI** | v1 只交付描述性分析 + 手动模板驱动报告 |
| **数据安全** | SQL 只读防注入、DW 最小权限、纯内网部署 |
| **数据权威** | 图表/表格不可手动编辑, 保持数据与 DW 一致 |
| **AI 辅助而非替代** | 文本可编辑、报告可调整、异常转人工 |
| **核心逻辑自研** | 仅 LangGraph 用于状态机编排, SQL/LLM 调用全部原生 Python |
| **测试保障确定性** | 规则引擎、RAG Router 等确定性模块单元测试覆盖, CI 门禁 |
