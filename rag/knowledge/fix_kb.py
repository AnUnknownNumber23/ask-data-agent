"""Fix Knowledge Base — common error-to-correction mappings, field aliases."""
import chromadb
from rag.embedding import get_embedding_function


class FixKB:
    def __init__(self, chroma_path: str):
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="fix_kb",
            metadata={"description": "Common SQL error corrections and field aliases"},
            embedding_function=get_embedding_function(),
        )

    def seed_defaults(self) -> int:
        """Seed with Olist-specific common error corrections."""
        entries = {
            "fix:order_date": "order_date is not a column. Use order_purchase_timestamp in orders table.",
            "fix:customer_name": "customer_name does not exist. Use customer_id with customers table, or customer_city/customer_state for location.",
            "fix:product_name": "product_name is not a column. Use product_category_name in products, joined via product_id.",
            "fix:customer_region": "customer_region is not a column. Use customer_state or customer_city in customers table.",
            "fix:seller_name": "seller_name does not exist. Use seller_id, seller_city, or seller_state in sellers table.",
            "fix:order_count": "order_count is not a direct column. Use COUNT(order_id) in queries.",
            "fix:total_sales_by_order_date": "order_date is not a column. Use order_purchase_timestamp with DATE_TRUNC for date grouping.",
            "fix:avg_price": "avg_price is not a column. Use AVG(order_items.price).",
            "fix:seller_name": "seller_name does not exist. Sellers have no name field — only seller_id, seller_city, seller_state. When listing sellers, always include seller_city and seller_state alongside seller_id so results are human-readable.",
            "fix:seller_id": "Seller IDs like '4869f7a5...' are hashes. Always include seller_city and seller_state in SELECT to make results readable.",
            # DuckDB function name corrections (common LLM mistakes)
            "fix:DATE_FORMAT": "DATE_FORMAT does not exist in DuckDB. Use STRFTIME(timestamp, '%Y-%m') instead. Example: STRFTIME(order_purchase_timestamp, '%Y-%m').",
            "fix:TO_DAYS": "TO_DAYS does not exist in DuckDB. Use DATEDIFF('day', start_date, end_date) instead. Example: DATEDIFF('day', order_purchase_timestamp, order_delivered_customer_date).",
            "fix:TO_CHAR": "TO_CHAR does not exist in DuckDB. Use STRFTIME(timestamp, format) instead. Example: STRFTIME(order_purchase_timestamp, '%B %d, %Y').",
            "fix:NOW": "NOW() works in DuckDB but returns current timestamp. For historical data (2016-2018), use actual date filters instead.",
            "fix:IFNULL": "IFNULL works in DuckDB but COALESCE is more standard. Use COALESCE(column, default_value).",
            "fix:GROUP_CONCAT": "GROUP_CONCAT works in DuckDB but STRING_AGG is more standard. Use STRING_AGG(column, ', ').",
            "fix:month": "There is no month column. Use DATE_TRUNC('month', order_purchase_timestamp) to extract month.",
            "fix:sales": "There is no sales column. Sales = SUM(order_items.price).",
            "fix:revenue": "Revenue is not a direct column. Use SUM(order_items.price) as revenue.",
            "fix:date": "Generic 'date' column not found. Use order_purchase_timestamp for order dates.",
        }
        count = 0
        for id_, doc in entries.items():
            self.collection.upsert(
                ids=[id_],
                documents=[doc],
                metadatas=[{"type": "fix"}],
            )
            count += 1
        return count

    def keyword_search(self, text: str, n: int = 3) -> list[dict]:
        """Keyword search for fix entries (supports underscore + CJK tokenization)."""
        from rag.knowledge.schema_kb import _tokenize
        tokens = _tokenize(text)
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
            if text.lower() in doc_lower:
                score += 0.5
            if score > 0:
                results.append({"id": rid, "document": doc, "metadata": meta, "distance": 1.0 - min(score, 0.95)})
        results.sort(key=lambda r: r["distance"])
        return results[:n]

    def lookup(self, error_msg: str) -> dict[str, str]:
        """Search for known fixes — keyword-first (vector unreliable with hash embeddings)."""
        # Always try keyword search first for reliability
        kw_results = self.keyword_search(error_msg, n=3)
        corrections = {}
        for r in kw_results:
            doc = r.get("document", "")
            rid = r.get("id", "")
            if "Use " in doc or "does not exist" in doc or "not a column" in doc:
                corrections[rid] = doc[:120]
        if corrections:
            return corrections
        # Fall back to vector search
        results = self.collection.query(query_texts=[error_msg], n_results=3)
        if results.get("ids") and results["ids"][0]:
            for i, rid in enumerate(results["ids"][0]):
                doc = results["documents"][0][i] if results.get("documents") else ""
                if " → " in doc or "Use " in doc:
                    corrections[rid] = doc
        return corrections
