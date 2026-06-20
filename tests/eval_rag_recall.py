"""RAG recall evaluation — 50 labeled queries, semantic matching."""
import os, asyncio, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

env_path = Path(os.getcwd()) / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

from api.dependencies import get_rag
from rag.router import Stage

GROUND_TRUTH = {
    # UNDERSTAND: needs table names + business terms
    "how many orders": (Stage.UNDERSTAND, {}, ["orders"]),
    "top product categories by sales": (Stage.UNDERSTAND, {}, ["products", "order_items", "gmv", "sales"]),
    "每个州的客户数量": (Stage.UNDERSTAND, {}, ["customers", "state"]),
    "average review score": (Stage.UNDERSTAND, {}, ["order_reviews", "review_score"]),
    "monthly sales trend": (Stage.UNDERSTAND, {}, ["orders", "order_items", "monthly"]),
    "信用卡支付占比": (Stage.UNDERSTAND, {}, ["order_payments", "credit_card"]),
    "东南区销售": (Stage.UNDERSTAND, {}, ["southeast", "customers", "state"]),
    "哪些品类利润率最高": (Stage.UNDERSTAND, {}, ["products", "margin", "毛利率"]),
    "sellers in Sao Paulo": (Stage.UNDERSTAND, {}, ["sellers"]),
    "orders delivered on time": (Stage.UNDERSTAND, {}, ["orders", "delivered"]),
    "payment installments analysis": (Stage.UNDERSTAND, {}, ["order_payments", "installments"]),
    "product weight and freight": (Stage.UNDERSTAND, {}, ["products", "order_items", "freight", "weight"]),
    "customer reviews": (Stage.UNDERSTAND, {}, ["order_reviews", "customers"]),
    "geographic distribution": (Stage.UNDERSTAND, {}, ["geolocation", "customers", "state"]),
    "客单价": (Stage.UNDERSTAND, {}, ["aov", "客单价", "order_items", "orders"]),

    # REASON: needs specific columns
    "count orders by status": (Stage.REASON, {"matched_tables": ["orders"]}, ["orders", "order_status"]),
    "total sales by product category": (Stage.REASON, {"matched_tables": ["products", "order_items"]}, ["products", "category", "price", "sales"]),
    "average freight by state": (Stage.REASON, {"matched_tables": ["customers", "order_items"]}, ["freight", "customers", "state"]),
    "monthly GMV in 2018": (Stage.REASON, {"matched_tables": ["orders", "order_items"]}, ["orders", "purchase_timestamp", "price", "monthly"]),
    "review score by seller": (Stage.REASON, {"matched_tables": ["order_reviews", "order_items"]}, ["review_score", "seller"]),
    "payment type distribution": (Stage.REASON, {"matched_tables": ["order_payments"]}, ["payment_type", "order_payments"]),
    "customer city with most orders": (Stage.REASON, {"matched_tables": ["customers", "orders"]}, ["customers", "city", "orders"]),
    "products with price above 100": (Stage.REASON, {"matched_tables": ["order_items"]}, ["price", "order_items"]),
    "delivery time analysis": (Stage.REASON, {"matched_tables": ["orders"]}, ["delivered", "purchase_timestamp", "orders"]),
    "seller revenue ranking": (Stage.REASON, {"matched_tables": ["order_items", "sellers"]}, ["seller", "price", "order_items"]),
    "每个州的客户数量": (Stage.REASON, {"matched_tables": ["customers"]}, ["customers", "state"]),
    "品类销售额排名": (Stage.REASON, {"matched_tables": ["products", "order_items"]}, ["products", "category", "price", "sales"]),
    "每月订单量趋势": (Stage.REASON, {"matched_tables": ["orders"]}, ["orders", "purchase_timestamp", "monthly"]),
    "卖家所在城市分布": (Stage.REASON, {"matched_tables": ["sellers"]}, ["sellers", "city"]),
    "各品类平均运费": (Stage.REASON, {"matched_tables": ["products", "order_items"]}, ["products", "freight"]),

    # REFLECT: needs Fix KB + Schema KB
    "column order_date not found": (Stage.REFLECT, {"error_message": "Column 'order_date' not found", "failed_sql": "SELECT order_date FROM orders"}, ["order_date", "order_purchase_timestamp"]),
    "function date_format does not exist": (Stage.REFLECT, {"error_message": "function date_format does not exist", "failed_sql": "SELECT DATE_FORMAT(...) FROM orders"}, ["date_format", "strftime"]),
    "column customer_name not found": (Stage.REFLECT, {"error_message": "Column 'customer_name' not found", "failed_sql": "SELECT customer_name FROM customers"}, ["customer_name", "customer_id"]),
    "function to_days does not exist": (Stage.REFLECT, {"error_message": "function to_days does not exist", "failed_sql": "SELECT TO_DAYS(...) FROM orders"}, ["to_days", "datediff"]),
    "column product_name not found": (Stage.REFLECT, {"error_message": "Column 'product_name' not found", "failed_sql": "SELECT product_name FROM products"}, ["product_name", "product_category"]),
    "column sales not found": (Stage.REFLECT, {"error_message": "Column 'sales' not found", "failed_sql": "SELECT sales FROM orders"}, ["sales", "price"]),
    "column revenue not found": (Stage.REFLECT, {"error_message": "Column 'revenue' not found", "failed_sql": "SELECT revenue FROM order_items"}, ["revenue", "price"]),
    "column month not found": (Stage.REFLECT, {"error_message": "Column 'month' not found", "failed_sql": "SELECT month FROM orders"}, ["month", "date_trunc"]),
    "function to_char does not exist": (Stage.REFLECT, {"error_message": "function to_char does not exist", "failed_sql": "SELECT TO_CHAR(...) FROM orders"}, ["to_char", "strftime"]),
    "column seller_name not found": (Stage.REFLECT, {"error_message": "Column 'seller_name' not found", "failed_sql": "SELECT seller_name FROM sellers"}, ["seller_name", "seller_id"]),

    # ANALYZE: needs analysis frameworks
    "show sales trend": (Stage.ANALYZE, {}, ["trend", "sales"]),
    "ranking analysis": (Stage.ANALYZE, {}, ["ranking"]),
    "compare regions": (Stage.ANALYZE, {}, ["comparison", "regional"]),
    "review analysis": (Stage.ANALYZE, {}, ["review_score"]),
    "payment breakdown": (Stage.ANALYZE, {}, ["payment"]),
    "growth rate": (Stage.ANALYZE, {}, ["growth", "trend"]),
    "margin analysis": (Stage.ANALYZE, {}, ["margin"]),
    "distribution breakdown": (Stage.ANALYZE, {}, ["breakdown"]),
    "sales by region": (Stage.ANALYZE, {}, ["regional", "sales"]),
    "排名分析": (Stage.ANALYZE, {}, ["ranking"]),
}


def recall_semantic(expected_keywords: list[str], retrieved_docs: list[str]) -> float:
    """Fraction of expected keywords found in at least one retrieved doc."""
    if not expected_keywords:
        return 1.0
    retrieved_text = " ".join(d.lower() for d in retrieved_docs)
    found = sum(1 for kw in expected_keywords if kw.lower() in retrieved_text)
    return found / len(expected_keywords)


def precision_semantic(expected_keywords: list[str], retrieved_docs: list[str]) -> float:
    """Fraction of retrieved docs containing expected keywords."""
    if not retrieved_docs:
        return 0.0
    ek = set(kw.lower() for kw in expected_keywords)
    relevant = 0
    for doc in retrieved_docs:
        doc_lower = doc.lower()
        if any(kw in doc_lower for kw in ek):
            relevant += 1
    return relevant / len(retrieved_docs)


async def main():
    rag = await get_rag()

    results = []
    by_stage = {s: {"recalls": [], "precisions": [], "count": 0} for s in Stage}

    for query, (stage, context, expected_kw) in GROUND_TRUTH.items():
        rag_result = await rag.retrieve(stage, query, context)
        # REFLECT returns corrections dict, other stages return documents
        docs = []
        for m in rag_result.matches:
            if "corrections" in m:
                for wrong, fix in m["corrections"].items():
                    docs.append(f"{wrong} -> {fix}")
            else:
                doc = m.get("document", "")
                if doc:
                    docs.append(doc)

        r = recall_semantic(expected_kw, docs)
        p = precision_semantic(expected_kw, docs)

        by_stage[stage]["recalls"].append(r)
        by_stage[stage]["precisions"].append(p)
        by_stage[stage]["count"] += 1

        missed = [kw for kw in expected_kw if kw.lower() not in " ".join(d.lower() for d in docs)]
        results.append((query[:60], stage.value, r, p, len(docs), missed))

    print("=" * 65)
    print("RAG Recall Evaluation — 50 queries, semantic keyword match")
    print("=" * 65)
    print()

    all_r = []; all_p = []
    for stage in [Stage.UNDERSTAND, Stage.REASON, Stage.REFLECT, Stage.ANALYZE]:
        st = by_stage[stage]
        if not st["recalls"]:
            continue
        avg_r = sum(st["recalls"]) / len(st["recalls"])
        avg_p = sum(st["precisions"]) / len(st["precisions"])
        all_r.extend(st["recalls"]); all_p.extend(st["precisions"])
        print(f"  {stage.value:12s}  recall={avg_r:.1%}  precision={avg_p:.1%}  n={st['count']}")

    print(f"  {'OVERALL':12s}  recall={sum(all_r)/len(all_r):.1%}  precision={sum(all_p)/len(all_p):.1%}  n={len(all_r)}")
    print()

    # Failures
    fails = [(q, s, m) for q, s, r, p, d, m in results if m]
    if fails:
        print(f"Queries with missing keywords ({len(fails)}/{len(results)}):")
        for q, s, m in fails[:8]:
            print(f"  [{s}] {q[:50]}")
            print(f"       missing: {m}")
    else:
        print("No missing keywords — perfect recall.")

    print()
    print("Per-query:")
    for q, s, r, p, d, m in results:
        icon = "+" if r >= 0.8 else ("~" if r >= 0.5 else "!")
        print(f"  [{icon}] r={r:.0%} p={p:.0%} d={d:2d} [{s:12s}] {q[:55]}")

if __name__ == "__main__":
    asyncio.run(main())
