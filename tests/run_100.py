"""Run 100 queries through agent. Run from project root with: python -m tests.run_100"""
import os, asyncio, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Load .env
env_path = Path(os.getcwd()) / ".env"
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

QUERIES = [
    # English: stats (10)
    "how many orders", "how many customers", "how many sellers", "how many products",
    "count of reviews", "total payments count", "how many geolocation records",
    "how many orders per status", "count customers by state", "count sellers by state",

    # English: rankings (10)
    "top 5 product categories by sales", "top 10 sellers by order count",
    "top 5 cities by customer count", "highest review score by category",
    "top 3 payment types by count", "most expensive product categories",
    "top 5 states by GMV", "rank categories by average freight",
    "top sellers by average review score", "best selling categories by quantity",

    # English: time series (10)
    "monthly sales trend in 2017", "daily orders in October 2017",
    "sales by month in 2018", "quarterly GMV trend in 2017",
    "year over year comparison 2017 vs 2018", "orders per week in December 2017",
    "monthly review count", "sales growth rate by month",
    "daily new orders in January 2018", "monthly freight cost trend",

    # English: filtering (10)
    "orders from SP state", "sales in southeast Brazil",
    "products in health beauty category", "orders paid with credit card",
    "reviews with score 5", "delivered orders count",
    "sellers from Sao Paulo city", "customers from Rio de Janeiro",
    "orders cancelled", "products heavier than 10kg",

    # English: complex JOIN (15)
    "average seller rating by state", "monthly GMV by payment type",
    "customer lifetime value by state", "freight cost percentage by category",
    "top categories in each state", "review score distribution by payment type",
    "correlation between product weight and freight", "seller concentration by category",
    "delivery time by state", "repeat purchase rate by category",
    "average payment installments by payment type", "customer city with highest order value",
    "products with highest freight to price ratio", "sellers with most diverse product range",
    "monthly order cancellation rate",

    # Chinese: stats + rankings + time (15)
    "有多少订单", "每个州的客户数量", "销售额最高的品类", "2017年每月GMV趋势",
    "信用卡支付占比", "东南区销售概况", "评分最高的品类", "圣保罗州卖家数量",
    "每个月的订单量", "平均运费是多少", "哪种支付方式最常用", "哪些品类利润率最高",
    "客户主要分布在哪些城市", "2018年第一季度销售额", "里约热内卢有多少客户",

    # Edge cases (15)
    "orders from Antarctica", "sales for November 2025", "products with negative price",
    "customers named John", "show me orders with customer_name", "count orders by xyz_col",
    "what is the meaning of life", "show products", "list all categories",
    "how many orders per status per month", "find products without reviews",
    "list sellers with no orders", "highest freight order",
    "earliest and latest order dates", "average number of items per order",

    # Complex analysis (15)
    "which state has highest freight cost per order",
    "find sellers whose average price is above overall average",
    "identify months with declining sales",
    "which categories have improving review scores over time",
    "compare weekend vs weekday order patterns",
    "which sellers ship fastest on average",
    "identify price outliers by category",
    "payment method preference by region",
    "customer repeat purchase rate",
    "seasonal demand patterns by category",
    "seller rating distribution",
    "order value distribution by state",
    "delivery performance by seller",
    "product category growth rate",
    "geographic sales concentration",
]


async def main():
    llm = get_llm()
    dw = get_dw()
    prompts = get_prompts()
    sql_eval = get_sql_evaluator()
    rag = await get_rag()

    passed = 0; failed = 0; clarify_n = 0; degrade_n = 0; escalate_n = 0
    total_time = 0; slowest = 0; failures = []

    for i, q in enumerate(QUERIES):
        tracer = ThinkingTracer()
        graph = build_agent_graph(llm, dw, rag, prompts, tracer, sql_eval)
        tracer.start(f"q{i}", q)

        state = {
            'messages': [], 'session_id': f'q{i}', 'user_query': q,
            'intent': {}, 'matched_tables': [], 'business_terms': {},
            'generated_sql': '', 'sql_error': None, 'retry_count': 0,
            'query_result': None, 'result_summary': '',
            'analysis_text': '', 'chart_config': None, 'evaluator_results': [],
            'clarification_question': None, 'degradation_message': None, 'escalation_ticket': None,
            'is_report_mode': False, 'report_outline': None, 'report_sections': [],
        }

        t0 = time.time()
        try:
            result = await asyncio.wait_for(graph.ainvoke(state), timeout=90)
            elapsed = time.time() - t0
            total_time += elapsed
            if elapsed > slowest: slowest = elapsed

            answer = (result.get('analysis_text', '')
                      or result.get('clarification_question', '')
                      or result.get('degradation_message', '')
                      or str(result.get('escalation_ticket', '')))

            if result.get('escalation_ticket'):
                status, escalate_n = "ESCALATE", escalate_n + 1; failed += 1
            elif result.get('clarification_question'):
                status, clarify_n = "CLARIFY", clarify_n + 1; passed += 1
            elif result.get('degradation_message'):
                status, degrade_n = "DEGRADE", degrade_n + 1; passed += 1
            elif not answer or answer.startswith('(crashed'):
                status = "EMPTY"; failed += 1
            else:
                status = "PASS"; passed += 1

        except asyncio.TimeoutError:
            elapsed = 90; status = "TIMEOUT"; failed += 1
            answer = "(timeout)"
        except Exception as e:
            elapsed = time.time() - t0; status = "CRASH"; failed += 1
            answer = f"({type(e).__name__})"
            failures.append(f"  [{i}] CRASH: {q[:60]} -> {type(e).__name__}")

        icon = {"PASS":"+","CLARIFY":"?","DEGRADE":"~","ESCALATE":"!","EMPTY":"0","TIMEOUT":"T","CRASH":"X"}[status]
        bar = f"[{icon}] {i+1:3d}/{len(QUERIES)} {status:8s} {elapsed:4.1f}s {q[:70]}"
        print(bar)

    avg = total_time / len(QUERIES) if QUERIES else 0
    total = passed + failed
    print()
    print("=" * 60)
    print(f"Total: {total}  Pass: {passed} ({passed*100//total}%)  Fail: {failed}")
    print(f"  PASS: {passed-clarify_n-degrade_n}  CLARIFY: {clarify_n}  DEGRADE: {degrade_n}  ESCALATE: {escalate_n}")
    print(f"  Avg: {avg:.1f}s  Slowest: {slowest:.1f}s  Total time: {total_time/60:.1f}min")
    if failures:
        print("Failures:")
        for f in failures[:10]:
            print(f)

    with open("/tmp/test_100_result.json", "w") as f:
        json.dump({"passed": passed, "failed": failed, "avg_time": avg, "failures": failures}, f)

if __name__ == "__main__":
    asyncio.run(main())
