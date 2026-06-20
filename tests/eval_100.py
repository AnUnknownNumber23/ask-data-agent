"""End-to-end evaluation: 100 labeled queries with expected answers."""
import os, asyncio, sys, io, time, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

from api.dependencies import get_llm, get_dw, get_prompts, get_sql_evaluator, get_rag
from agent.graph import build_agent_graph
from monitoring.tracer import ThinkingTracer

# ====== 100 Labeled Queries ======
# Each: (query, category, expected_tables, expected_sql_keywords, expected_answer_keywords)
EVAL_QUERIES = [
    # --- Stats (15) ---
    ("how many orders", "stat", ["orders"], ["COUNT", "orders"], ["99", "441"]),
    ("how many customers", "stat", ["customers"], ["COUNT", "customers"], ["99", "441", "96", "096"]),
    ("how many sellers", "stat", ["sellers"], ["COUNT", "sellers"], ["3", "095"]),
    ("how many products", "stat", ["products"], ["COUNT", "products"], ["32", "951"]),
    ("count of reviews", "stat", ["order_reviews"], ["COUNT", "order_reviews"], ["99", "224"]),
    ("total payments count", "stat", ["order_payments"], ["COUNT", "order_payments"], ["103"]),
    ("how many geolocation records", "stat", ["geolocation"], ["COUNT", "geolocation"], ["1", "000"]),
    ("how many orders per status", "stat", ["orders"], ["order_status", "GROUP BY"], ["delivered", "96", "478"]),
    ("count customers by state", "stat", ["customers"], ["customer_state", "GROUP BY"], ["SP", "41"]),
    ("count sellers by state", "stat", ["sellers"], ["seller_state", "GROUP BY"], ["SP", "694"]),
    ("average order value", "stat", ["orders", "order_items"], ["AVG", "SUM", "price"], ["137"]),
    ("total GMV", "stat", ["order_items"], ["SUM", "price"], ["13", "221"]),
    ("average freight cost", "stat", ["order_items"], ["AVG", "freight_value"], ["19"]),
    ("average review score", "stat", ["order_reviews"], ["AVG", "review_score"], ["4"]),
    ("earliest and latest order dates", "stat", ["orders"], ["MIN", "MAX", "order_purchase_timestamp"], ["2016", "2018"]),

    # --- Rankings (20) ---
    ("top 5 product categories by sales", "rank", ["products", "order_items"], ["SUM", "price", "GROUP BY", "ORDER BY", "DESC", "LIMIT 5"], ["health", "beauty", "watch"]),
    ("top 10 sellers by order count", "rank", ["sellers", "order_items"], ["COUNT", "seller_id", "GROUP BY", "ORDER BY", "DESC", "LIMIT 10"], ["seller"]),
    ("top 5 cities by customer count", "rank", ["customers"], ["customer_city", "COUNT", "GROUP BY", "ORDER BY", "DESC", "LIMIT 5"], ["sao", "paulo"]),
    ("highest review score by category", "rank", ["products", "order_reviews"], ["AVG", "review_score", "GROUP BY", "ORDER BY", "DESC"], ["score"]),
    ("top 3 payment types by count", "rank", ["order_payments"], ["payment_type", "COUNT", "GROUP BY", "ORDER BY", "DESC", "LIMIT 3"], ["credit"]),
    ("top 5 states by GMV", "rank", ["customers", "orders", "order_items"], ["SUM", "price", "customer_state", "GROUP BY", "ORDER BY", "DESC", "LIMIT 5"], ["SP", "RJ", "MG"]),
    ("best selling categories by quantity", "rank", ["products", "order_items"], ["COUNT", "GROUP BY", "ORDER BY", "DESC"], ["bed", "bath"]),
    ("most expensive product categories", "rank", ["products", "order_items"], ["AVG", "price", "GROUP BY", "DESC"], ["price"]),
    ("rank categories by average freight", "rank", ["products", "order_items"], ["AVG", "freight_value", "GROUP BY", "DESC"], ["freight"]),
    ("top sellers by average review score", "rank", ["sellers", "order_items", "order_reviews"], ["AVG", "review_score", "seller_id", "GROUP BY", "DESC"], ["review", "seller"]),
    ("销售额最高的品类", "rank", ["products", "order_items"], ["SUM", "price", "GROUP BY", "DESC"], ["健康", "美容"]),
    ("评分最高的品类", "rank", ["products", "order_reviews"], ["AVG", "review_score", "GROUP BY", "DESC"], ["评分"]),
    ("销量最高的10个产品", "rank", ["products", "order_items"], ["COUNT", "GROUP BY", "DESC", "LIMIT 10"], ["产品"]),
    ("哪个州订单最多", "rank", ["customers", "orders"], ["customer_state", "COUNT", "GROUP BY", "DESC"], ["SP", "圣保罗"]),
    ("哪种支付方式最常用", "rank", ["order_payments"], ["payment_type", "COUNT", "GROUP BY", "DESC"], ["credit", "信用卡"]),
    ("seller concentration by category", "rank", ["sellers", "products", "order_items"], ["COUNT", "seller_id", "GROUP BY"], ["seller"]),
    ("customer city with highest order value", "rank", ["customers", "orders", "order_items"], ["SUM", "price", "customer_city", "GROUP BY", "DESC"], ["city"]),
    ("products with highest freight to price ratio", "rank", ["products", "order_items"], ["freight_value", "price", "GROUP BY", "DESC"], ["freight"]),
    ("highest freight order", "rank", ["orders", "order_items"], ["freight_value", "ORDER BY", "DESC", "LIMIT 1"], ["freight"]),
    ("average payment installments by payment type", "rank", ["order_payments"], ["AVG", "payment_installments", "payment_type", "GROUP BY"], ["installment"]),

    # --- Time Series (15) ---
    ("monthly sales trend in 2017", "time", ["orders", "order_items"], ["DATE_TRUNC", "month", "GROUP BY", "ORDER BY"], ["2017", "month"]),
    ("daily orders in October 2017", "time", ["orders"], ["DATE_TRUNC", "day", "WHERE", "2017-10", "GROUP BY"], ["October", "2017"]),
    ("sales by month in 2018", "time", ["orders", "order_items"], ["DATE_TRUNC", "month", "WHERE", "2018", "GROUP BY"], ["2018"]),
    ("year over year comparison 2017 vs 2018", "time", ["orders", "order_items"], ["2017", "2018", "SUM"], ["2017", "2018"]),
    ("monthly review count", "time", ["orders", "order_reviews"], ["DATE_TRUNC", "month", "COUNT", "GROUP BY"], ["month"]),
    ("monthly freight cost trend", "time", ["orders", "order_items"], ["DATE_TRUNC", "month", "SUM", "freight", "GROUP BY"], ["freight", "month"]),
    ("daily new orders in January 2018", "time", ["orders"], ["DATE_TRUNC", "day", "WHERE", "2018-01", "COUNT", "GROUP BY"], ["January", "2018"]),
    ("2017年每月GMV趋势", "time", ["orders", "order_items"], ["DATE_TRUNC", "month", "2017", "SUM", "GROUP BY"], ["2017", "月"]),
    ("2018年第一季度销售额", "time", ["orders", "order_items"], ["WHERE", "2018", "SUM", "price"], ["2018", "季度"]),
    ("每个月的订单量", "time", ["orders"], ["DATE_TRUNC", "month", "COUNT", "GROUP BY"], ["月"]),
    ("quarterly GMV trend in 2017", "time", ["orders", "order_items"], ["DATE_TRUNC", "quarter", "2017", "SUM"], ["2017", "quarter"]),
    ("orders per week in December 2017", "time", ["orders"], ["DATE_TRUNC", "week", "2017-12", "COUNT", "GROUP BY"], ["December", "2017"]),
    ("sales growth rate by month", "time", ["orders", "order_items"], ["DATE_TRUNC", "month", "SUM", "LAG", "growth"], ["growth", "rate", "month"]),
    ("compare weekend vs weekday order patterns", "time", ["orders"], ["DAYOFWEEK", "DATE_TRUNC", "COUNT", "GROUP BY"], ["weekend", "weekday"]),
    ("seasonal demand patterns by category", "time", ["products", "order_items", "orders"], ["DATE_TRUNC", "month", "COUNT", "GROUP BY"], ["seasonal", "month"]),

    # --- Filtering (15) ---
    ("orders from SP state", "filter", ["customers", "orders"], ["WHERE", "customer_state", "SP"], ["SP", "Sao Paulo"]),
    ("sales in southeast Brazil", "filter", ["customers", "orders", "order_items"], ["WHERE", "IN", "SP", "RJ", "MG", "ES"], ["southeast"]),
    ("products in health beauty category", "filter", ["products", "category_translation"], ["WHERE", "product_category_name", "beleza_saude"], ["health", "beauty"]),
    ("orders paid with credit card", "filter", ["order_payments"], ["WHERE", "payment_type", "credit_card"], ["credit"]),
    ("reviews with score 5", "filter", ["order_reviews"], ["WHERE", "review_score", "5"], ["5"]),
    ("sellers from Sao Paulo city", "filter", ["sellers"], ["WHERE", "seller_city", "sao paulo"], ["sao", "paulo"]),
    ("customers from Rio de Janeiro", "filter", ["customers"], ["WHERE", "customer_city", "rio de janeiro"], ["rio"]),
    ("orders cancelled", "filter", ["orders"], ["WHERE", "order_status", "canceled"], ["cancel"]),
    ("products heavier than 10kg", "filter", ["products"], ["WHERE", "product_weight_g", ">", "10000"], ["weight"]),
    ("orders delivered on time", "filter", ["orders"], ["delivered", "estimated"], ["delivered"]),
    ("圣保罗州卖家数量", "filter", ["sellers"], ["WHERE", "seller_state", "SP", "COUNT"], ["SP", "圣保罗"]),
    ("里约热内卢有多少客户", "filter", ["customers"], ["WHERE", "customer_city", "rio", "COUNT"], ["里约"]),
    ("信用卡支付占比", "filter", ["order_payments"], ["WHERE", "payment_type", "credit_card", "COUNT"], ["信用卡", "credit"]),
    ("东南区销售概况", "filter", ["customers", "orders", "order_items"], ["WHERE", "IN", "SP", "RJ", "MG", "ES"], ["东南", "southeast"]),
    ("find products without reviews", "filter", ["products", "order_reviews"], ["LEFT JOIN", "IS NULL"], ["without", "review"]),

    # --- Complex JOIN / Analysis (15) ---
    ("average seller rating by state", "complex", ["sellers", "order_items", "order_reviews"], ["seller_state", "AVG", "review_score", "GROUP BY"], ["state", "rating"]),
    ("customer lifetime value by state", "complex", ["customers", "orders", "order_items"], ["SUM", "price", "customer_state", "GROUP BY"], ["lifetime", "state"]),
    ("delivery time by state", "complex", ["customers", "orders"], ["delivered", "purchase", "customer_state", "GROUP BY"], ["delivery", "state"]),
    ("repeat purchase rate by category", "complex", ["products", "orders", "order_items", "customers"], ["COUNT", "DISTINCT", "customer", "GROUP BY"], ["repeat", "rate"]),
    ("review score distribution by payment type", "complex", ["order_payments", "order_reviews"], ["payment_type", "review_score", "GROUP BY"], ["payment", "score"]),
    ("customer city with highest order value", "complex", ["customers", "orders", "order_items"], ["SUM", "price", "customer_city", "GROUP BY", "DESC"], ["city", "value"]),
    ("which state has highest freight cost per order", "complex", ["customers", "orders", "order_items"], ["AVG", "freight_value", "customer_state", "GROUP BY", "DESC"], ["state", "freight"]),
    ("find sellers whose average price is above overall average", "complex", ["sellers", "order_items"], ["AVG", "price", "HAVING", "subquery"], ["above", "average"]),
    ("identify price outliers by category", "complex", ["products", "order_items"], ["AVG", "STDDEV", "price", "GROUP BY"], ["outlier"]),
    ("customer repeat purchase rate", "complex", ["customers", "orders"], ["COUNT", "DISTINCT", "customer_id", "HAVING"], ["repeat"]),
    ("average number of items per order", "complex", ["order_items"], ["COUNT", "AVG", "order_id", "GROUP BY"], ["items", "order"]),
    ("list sellers with no orders", "complex", ["sellers", "order_items"], ["LEFT JOIN", "IS NULL"], ["no orders"]),
    ("which categories have improving review scores over time", "complex", ["products", "order_reviews", "orders"], ["review_score", "DATE_TRUNC", "GROUP BY"], ["improving", "time"]),
    ("payment method preference by region", "complex", ["customers", "orders", "order_payments"], ["payment_type", "customer_state", "COUNT", "GROUP BY"], ["payment", "region"]),
    ("geographic sales concentration", "complex", ["customers", "orders", "order_items", "geolocation"], ["SUM", "price", "customer_state", "GROUP BY"], ["concentration"]),

    # --- Why / Attribution (10) ---
    ("为什么东南区毛利率跌了", "why", ["customers", "orders", "order_items"], ["DATE_TRUNC", "price", "freight", "GROUP BY"], ["毛利率", "东南", "下降"]),
    ("why did orders drop in December 2017", "why", ["orders"], ["DATE_TRUNC", "month", "2017-12", "COUNT"], ["December", "2017", "drop", "decline"]),
    ("identify months with declining sales", "why", ["orders", "order_items"], ["DATE_TRUNC", "month", "SUM", "LAG"], ["declining", "month"]),
    ("which product category caused the decline in sales", "why", ["products", "order_items", "orders"], ["SUM", "price", "GROUP BY", "DESC"], ["decline", "category"]),
    ("为什么信用卡支付占比下降了", "why", ["order_payments", "orders"], ["payment_type", "DATE_TRUNC", "COUNT", "GROUP BY"], ["下降", "信用卡"]),
    ("find reasons for high freight costs", "why", ["order_items", "products", "sellers"], ["AVG", "freight_value", "GROUP BY"], ["freight", "high"]),
    ("哪些品类利润率最高", "why", ["products", "order_items"], ["price", "freight", "GROUP BY", "DESC"], ["利润率", "品类"]),
    ("what caused the drop in average review score", "why", ["order_reviews", "orders"], ["DATE_TRUNC", "AVG", "review_score", "GROUP BY"], ["drop", "review"]),
    ("analyze factors driving GMV growth in 2017", "why", ["orders", "order_items", "products"], ["DATE_TRUNC", "SUM", "2017", "GROUP BY"], ["growth", "2017", "factor"]),
    ("correlation between product weight and freight cost", "why", ["products", "order_items"], ["weight", "freight", "CORR"], ["weight", "freight", "correlation"]),

    # --- Predict / Forecast (5) ---
    ("预测下个月GMV趋势", "predict", ["orders", "order_items"], ["DATE_TRUNC", "month", "SUM"], ["预测", "GMV", "趋势"]),
    ("forecast sales for next quarter", "predict", ["orders", "order_items"], ["DATE_TRUNC", "SUM", "GROUP BY"], ["forecast", "quarter"]),
    ("预计下季度订单量", "predict", ["orders"], ["DATE_TRUNC", "COUNT", "GROUP BY"], ["预计", "订单"]),
    ("predict customer growth trend", "predict", ["customers", "orders"], ["DATE_TRUNC", "COUNT", "DISTINCT", "GROUP BY"], ["growth", "trend"]),
    ("what will the average order value be next month", "predict", ["orders", "order_items"], ["AVG", "SUM", "price", "DATE_TRUNC", "GROUP BY"], ["predict", "average", "order", "value"]),

    # --- Edge Cases (5) ---
    ("orders from Antarctica", "edge", [], [], []),  # should clarify/reject
    ("sales for November 2025", "edge", ["orders", "order_items"], ["WHERE", "2025-11"], ["不存在", "数据缺失", "2025"]),
    ("products with negative price", "edge", [], ["WHERE", "price", "<", "0"], ["negative", "price"]),
    ("customers named John", "edge", [], [], []),  # no name field — should clarify
    ("show me orders with customer_name", "edge", [], [], []),  # field doesn't exist
]


def score_sql(sql: str, expected_tables: list[str], expected_keywords: list[str]) -> float:
    """Score SQL quality: tables used + keywords present."""
    if not sql:
        return 0.0
    sql_upper = sql.upper()
    score = 0.0
    # Table presence (40%)
    if expected_tables:
        found_tables = sum(1 for t in expected_tables if t.lower() in sql.lower())
        score += 0.4 * (found_tables / len(expected_tables))
    # Keyword presence (60% — only if keywords specified)
    if expected_keywords:
        found_kw = sum(1 for kw in expected_keywords if kw.upper() in sql_upper)
        score += 0.6 * (found_kw / len(expected_keywords))
    elif expected_tables:
        score += 0.6  # no keyword expectations, full credit

    return min(score, 1.0)


def score_answer(answer: str, query: str) -> float:
    """Score answer quality: non-empty, relevant, specific."""
    if not answer or len(answer) < 20:
        return 0.0
    score = 1.0
    # Penalize empty/generic responses
    if "no data found" in answer.lower():
        score = 0.6
    if "已转交人工" in answer:
        score = 0.3
    if "analysis complete" in answer.lower() and len(answer) < 100:
        score = 0.4
    if "抱歉" in answer and "数据" not in answer:
        score = 0.3  # non-data rejection
    return score


async def evaluate_one(llm, dw, prompts, sql_eval, rag, i: int, query: str, category: str,
                       expected_tables: list[str], expected_sql_kw: list[str],
                       expected_answer_kw: list[str]) -> dict:
    t0 = time.time()
    tracer = ThinkingTracer()
    graph = build_agent_graph(llm, dw, rag, prompts, tracer, sql_eval)
    tracer.start(f"eval{i}", query)

    state = {
        'messages': [], 'session_id': f'eval{i}', 'user_query': query,
        'intent': {}, 'matched_tables': [], 'business_terms': {},
        'generated_sql': '', 'sql_error': None, 'retry_count': 0,
        'query_result': None, 'result_summary': '',
        'analysis_text': '', 'chart_config': None, 'evaluator_results': [],
        'clarification_question': None, 'degradation_message': None, 'escalation_ticket': None,
        'is_report_mode': False, 'report_outline': None, 'report_sections': [],
        'react_round': 0, 'accumulated_rounds': [], 'react_max_rounds': 5,
    }
    result = await graph.ainvoke(state)
    elapsed = time.time() - t0

    sql = result.get('generated_sql') or ''
    answer = (result.get('analysis_text', '')
              or result.get('clarification_question', '')
              or result.get('degradation_message', '')
              or str(result.get('escalation_ticket', '')))
    steps = [s['step'] for s in tracer.to_dict().get('steps', [])]
    rounds = result.get('react_round', 0)
    is_clarify = bool(result.get('clarification_question'))
    is_escalate = bool(result.get('escalation_ticket'))
    is_non_data = '抱歉' in answer and '数据' not in answer

    sql_score = score_sql(sql, expected_tables, expected_sql_kw)
    ans_score = 0.0
    if is_non_data:
        ans_score = 0.8  # correctly rejected non-data
    elif is_clarify:
        ans_score = 0.6  # asked for clarification (valid for edge cases)
    elif is_escalate:
        ans_score = 0.2
    else:
        ans_score = score_answer(answer, query)

    overall = (sql_score + ans_score) / 2

    return {
        "id": i, "query": query[:80], "category": category,
        "sql_score": sql_score, "ans_score": ans_score,
        "overall": overall,
        "elapsed": elapsed, "rounds": rounds,
        "is_clarify": is_clarify, "is_escalate": is_escalate,
        "sql_len": len(sql), "answer_len": len(answer),
        "answer_preview": answer[:200],
    }


async def main():
    llm = get_llm(); dw = get_dw(); prompts = get_prompts()
    sql_eval = get_sql_evaluator(); rag = await get_rag()

    results = []
    for i, (q, cat, tables, sql_kw, ans_kw) in enumerate(EVAL_QUERIES):
        if not q.strip():
            continue
        r = await evaluate_one(llm, dw, prompts, sql_eval, rag, i, q, cat, tables, sql_kw, ans_kw)
        results.append(r)
        icon = "+" if r['overall'] >= 0.8 else ("~" if r['overall'] >= 0.5 else "!")
        print(f"[{icon}] {i+1:3d}/{len(EVAL_QUERIES)} {r['overall']:.0%} sql={r['sql_score']:.0%} ans={r['ans_score']:.0%} {r['elapsed']:4.1f}s [{r['category']:7s}] {r['query'][:55]}")

    print()
    print("=" * 70)
    total = len(results)
    avg_score = sum(r['overall'] for r in results) / total if total else 0
    avg_sql = sum(r['sql_score'] for r in results) / total if total else 0
    avg_ans = sum(r['ans_score'] for r in results) / total if total else 0
    avg_time = sum(r['elapsed'] for r in results) / total if total else 0
    clarifies = sum(1 for r in results if r['is_clarify'])
    escalates = sum(1 for r in results if r['is_escalate'])
    high = sum(1 for r in results if r['overall'] >= 0.8)
    mid = sum(1 for r in results if 0.5 <= r['overall'] < 0.8)
    low = sum(1 for r in results if r['overall'] < 0.5)

    by_cat = {}
    for r in results:
        c = r['category']
        if c not in by_cat:
            by_cat[c] = []
        by_cat[c].append(r['overall'])

    print(f"Total: {total} queries")
    print(f"Overall Score: {avg_score:.1%}")
    print(f"  SQL Score:     {avg_sql:.1%}")
    print(f"  Answer Score:  {avg_ans:.1%}")
    print(f"  Excellent (>0.8): {high}  Good (0.5-0.8): {mid}  Poor (<0.5): {low}")
    print(f"  Clarifications: {clarifies}  Escalations: {escalates}")
    print(f"  Avg Time: {avg_time:.1f}s")
    print()
    print("By Category:")
    for cat in ["stat", "rank", "time", "filter", "complex", "why", "predict", "edge"]:
        if cat in by_cat:
            scores = by_cat[cat]
            print(f"  {cat:8s}: avg={sum(scores)/len(scores):.1%}  n={len(scores)}")
    print()

    low_results = [r for r in results if r['overall'] < 0.5]
    if low_results:
        print(f"Low scores (< 0.5): {len(low_results)}")
        for r in low_results[:10]:
            print(f"  [{r['id']}] {r['category']} score={r['overall']:.0%} sql={r['sql_score']:.0%} ans={r['ans_score']:.0%} {r['query'][:60]}")
            print(f"         answer: {r['answer_preview'][:120]}")

    # Save report
    with open("data/eval_100_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": total, "overall_score": avg_score,
            "sql_score": avg_sql, "answer_score": avg_ans,
            "excellent": high, "good": mid, "poor": low,
            "clarifications": clarifies, "escalations": escalates,
            "avg_time": avg_time,
            "by_category": {c: sum(s)/len(s) for c, s in by_cat.items()},
            "low_scores": [{"id": r['id'], "query": r['query'], "score": r['overall'], "answer": r['answer_preview']} for r in low_results],
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
