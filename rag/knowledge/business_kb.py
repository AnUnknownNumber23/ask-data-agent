"""Business Knowledge Base — metric definitions, term mappings, common SQL patterns."""
import re
import chromadb
from rag.embedding import get_embedding_function


def _add_cjk_tokens(text: str, tokens: list[str]) -> None:
    """Add Chinese/Japanese/Korean bigram tokens for queries without spaces."""
    cjk = re.findall(r'[一-鿿㐀-䶿豈-﫿]+', text)
    for segment in cjk:
        # Bigrams: "东南区毛利率" → ["东南", "南区", "区毛", "毛利", "利率"]
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
        # Also add individual characters as unigrams
        for ch in segment:
            tokens.append(ch)


class BusinessKB:
    def __init__(self, chroma_path: str):
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="business_kb",
            metadata={"description": "Business metric definitions and term mappings"},
            embedding_function=get_embedding_function(),
        )

    def seed_defaults(self) -> int:
        """Seed with Olist-specific business knowledge."""
        entries = {
            "biz:gmv": "GMV (Gross Merchandise Value) = SUM(order_items.price). Total sales value before deductions.",
            "biz:margin": "Gross Margin = (SUM(price) - SUM(freight_value)) / SUM(price). Profitability per order.",
            "biz:aov": "AOV (Average Order Value) = AVG(SUM(price) per order). Average spend per order.",
            "biz:review_score": "Review Score is in order_reviews.review_score, range 1-5. Higher is better.",
            "biz:southeast": "Southeast Brazil = customer_state IN ('SP','RJ','MG','ES'). Most populated region.",
            "biz:south": "South Brazil = customer_state IN ('PR','SC','RS').",
            "biz:northeast": "Northeast Brazil = customer_state IN ('BA','PE','CE','MA','PB','RN','AL','PI','SE').",
            "biz:order_status": "order_status values: delivered, shipped, canceled, unavailable, approved, processing, created, invoiced.",
            "biz:payment_types": "payment_type values: credit_card, boleto, voucher, debit_card.",
            # Intent mapping: guide the LLM to the right aggregation level
            "biz:产品": "产品 (Products) = products 表。当用户问有哪些/什么产品时，默认返回 product_category_name 的列表（去重），而不是单个 product_id。应该SELECT DISTINCT product_category_name FROM products。查询产品时优先展示品类而非ID。",
            "biz:卖家": "卖家 (Sellers) = sellers 表。当用户问有哪些卖家时，返回 seller_city/seller_state 的分布或数量，而非单个 seller_id。",
            "biz:有哪些": "有哪些/列出/显示 (List/Show) = 当用户问列出或显示时，默认返回去重的分类列表，而不是原始ID。使用 DISTINCT 或 GROUP BY 来聚合。",

            # Prediction / forecasting terms
            "biz:预测": "预测 (Forecast) = 基于历史趋势推断未来。数据库时间范围 2016-09 到 2018-10。预测应基于已有趋势外推，不要用未来日期过滤。Table: orders, order_items。",
            "biz:趋势": "趋势 (Trend) = 时间序列的变化方向。使用 DATE_TRUNC 按月/季度聚合，观察增长或下降模式。Uses tables: orders, order_items。",
            "biz:下个月": "下个月 (Next Month) = 数据的最后一个月之后。数据库最后日期是 2018-10，所以'下个月'指基于趋势预测的 2018-11。不要用 CURRENT_DATE 或 NOW()。",

            # Chinese business terms
            "biz:毛利率": "毛利率 (Gross Margin) = (SUM(order_items.price) - SUM(order_items.freight_value)) / SUM(order_items.price). Uses tables: order_items. 毛利率在 order_items 表中计算。",
            "biz:东南区": "东南区 (Southeast Brazil) = customer_state IN ('SP','RJ','MG','ES'). Uses tables: customers, geolocation. 东南区客户在 customers 表中按 state 筛选。",
            "biz:客单价": "客单价 (AOV Average Order Value) = SUM(order_items.price) / COUNT(DISTINCT orders.order_id). Uses tables: order_items, orders. 客单价需要 order_items 和 orders 表。",
            "biz:销售额": "销售额 (Sales Revenue/GMV) = SUM(order_items.price). Uses tables: order_items. 销售额在 order_items 表中。",
            "biz:评分": "评分 (Review Score) = order_reviews.review_score, range 1-5. Uses tables: order_reviews, orders. 评分在 order_reviews 表中。",
            "biz:上个月": "上个月 (Last Month) = use order_purchase_timestamp with date functions. Filters on orders.order_purchase_timestamp. 上个月数据通过 orders 表的时间过滤获取。",
        }
        count = 0
        for id_, doc in entries.items():
            self.collection.upsert(
                ids=[id_],
                documents=[doc],
                metadatas=[{"type": "business_rule"}],
            )
            count += 1
        return count

    def search_terms(self, query: str, n: int = 5) -> list[dict]:
        """Search business terms — merges vector + keyword results."""
        vec_results = self.collection.query(query_texts=[query], n_results=n)
        vec_formatted = self._format(vec_results)
        # Always also run keyword search (vector unreliable with hash embeddings)
        kw_formatted = self.keyword_search(query, n=n)
        # Merge with weighted scores (keyword distances artificially low)
        seen = set()
        merged = []
        for r in vec_formatted:
            rid = r.get("id", "")
            if rid not in seen:
                seen.add(rid)
                r["_score"] = 0.6 * (1.0 - min(r.get("distance", 1.0), 1.0))
                merged.append(r)
        for r in kw_formatted:
            rid = r.get("id", "")
            kw_dist = r.get("distance", 0.5)
            normalized = 1.0 - min(kw_dist * 4, 1.0)
            if rid not in seen:
                seen.add(rid)
                r["_score"] = 0.4 * max(normalized, 0.0)
                merged.append(r)
            else:
                for existing in merged:
                    if existing.get("id") == rid:
                        existing["_score"] = existing["_score"] + 0.4 * max(normalized, 0.0)
                        break
        merged.sort(key=lambda r: r.get("_score", 0), reverse=True)
        for r in merged:
            r.pop("_score", None)
        return merged[:n]

    def keyword_search(self, query: str, n: int = 5) -> list[dict]:
        """Fallback keyword search (supports Chinese + underscore splitting)."""
        from rag.knowledge.schema_kb import _tokenize
        tokens = _tokenize(query)
        results = []
        all_docs = self.collection.get()
        if not all_docs["ids"]:
            return results
        for i, rid in enumerate(all_docs["ids"]):
            doc = (all_docs.get("documents") or [""])[i] if all_docs.get("documents") else ""
            meta = (all_docs.get("metadatas") or [{}])[i] if all_docs.get("metadatas") else {}
            doc_lower = doc.lower()
            score = 0.0
            for token in tokens:
                if token and token in doc_lower:
                    score += 0.3
            if query.lower() in doc_lower:
                score += 0.5
            if score > 0:
                results.append({"id": rid, "document": doc, "metadata": meta, "distance": 1.0 - min(score, 0.95)})
        results.sort(key=lambda r: r["distance"])
        return results[:n]

    def _format(self, results: dict) -> list[dict]:
        formatted = []
        if results.get("ids") and results["ids"][0]:
            for i, rid in enumerate(results["ids"][0]):
                formatted.append({
                    "id": rid,
                    "document": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                })
        return formatted
