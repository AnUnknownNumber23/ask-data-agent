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

    def lookup(self, error_msg: str) -> dict[str, str]:
        """Search for known fixes matching the error message."""
        results = self.collection.query(query_texts=[error_msg], n_results=3)
        corrections = {}
        if results.get("ids") and results["ids"][0]:
            for i, rid in enumerate(results["ids"][0]):
                doc = results["documents"][0][i] if results.get("documents") else ""
                if " → " in doc or "Use " in doc:
                    corrections[rid] = doc
        return corrections
