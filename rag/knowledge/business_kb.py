"""Business Knowledge Base — metric definitions, term mappings, common SQL patterns."""
import chromadb


class BusinessKB:
    def __init__(self, chroma_path: str):
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="business_kb",
            metadata={"description": "Business metric definitions and term mappings"},
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
        results = self.collection.query(query_texts=[query], n_results=n)
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
