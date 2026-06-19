"""Analytics Knowledge Base — analysis frameworks, visualization suggestions, patterns."""
import chromadb
from rag.embedding import get_embedding_function


class AnalyticsKB:
    """Stores reusable analysis frameworks for the ANALYZE stage."""

    def __init__(self, chroma_path: str):
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="analytics_kb",
            metadata={"description": "Analysis frameworks and visualization patterns"},
            embedding_function=get_embedding_function(),
        )

    def seed_defaults(self) -> int:
        entries = {
            "analytics:trend": (
                "Trend Analysis Framework: "
                "1) Identify overall direction (up/down/stable). "
                "2) Note any inflection points or sudden changes. "
                "3) Compare early vs late periods for magnitude of change. "
                "4) If multiple series, compare their relative trajectories. "
                "Chart: line chart with time on x-axis."
            ),
            "analytics:ranking": (
                "Ranking Analysis Framework: "
                "1) Identify top 3-5 items by metric value. "
                "2) Note the gap between #1 and #2 (is there a dominant leader?). "
                "3) Calculate cumulative share of top N items. "
                "4) Mention the long tail if visible. "
                "Chart: horizontal bar chart sorted by value."
            ),
            "analytics:breakdown": (
                "Breakdown/Distribution Framework: "
                "1) Identify the largest category and its percentage. "
                "2) Note if distribution is concentrated ( Pareto: 80/20 ) or evenly spread. "
                "3) Highlight any surprising or unusually small categories. "
                "4) Recommend drill-down for the top category. "
                "Chart: pie or treemap for proportions, bar chart for counts."
            ),
            "analytics:comparison": (
                "Comparison Framework: "
                "1) State the absolute difference between compared items. "
                "2) Calculate percentage change (increase or decrease). "
                "3) If comparing time periods, note seasonality patterns. "
                "4) Flag if the difference is significant (more than 20% change). "
                "Chart: grouped bar chart or dual-axis line chart."
            ),
            "analytics:growth": (
                "Growth Analysis Framework: "
                "1) Calculate period-over-period growth rate. "
                "2) Identify if growth is accelerating or decelerating. "
                "3) Note any negative growth periods and possible causes. "
                "4) Project forward if trend is consistent. "
                "Chart: line chart with trend line overlay."
            ),
            "analytics:review_score": (
                "Review Score Analysis: "
                "1) Show average score and distribution across 1-5 scale. "
                "2) Identify categories/sellers with highest and lowest scores. "
                "3) Note if high-volume items have different scores from low-volume. "
                "4) Correlation between score and price/freight. "
                "Chart: histogram of scores, scatter plot of score vs price."
            ),
            "analytics:payment": (
                "Payment Analysis: "
                "1) Distribution of payment types by count and value. "
                "2) Average installments per payment type. "
                "3) Note if high-value orders prefer certain payment methods. "
                "4) Compare payment behavior across regions. "
                "Chart: stacked bar for payment type mix, pie for proportions."
            ),
            "analytics:regional": (
                "Regional Analysis: "
                "1) Rank states/cities by the metric. "
                "2) Calculate per-capita or per-order values for fair comparison. "
                "3) Identify geographic clusters (e.g. Southeast dominates). "
                "4) Note any outliers: regions with unusually high or low values. "
                "Chart: map (if coordinates available) or horizontal bar chart."
            ),
            "analytics:sales": (
                "Sales Revenue Analysis: "
                "GMV (Gross Merchandise Value) = SUM(order_items.price). "
                "Key metrics: total GMV, average order value (AOV = GMV / orders), "
                "month-over-month growth. Break down by category, region, time. "
                "Watch for: freight cost impact on profitability. "
                "Chart: line chart for trends, bar chart for category breakdown."
            ),
            "analytics:margin": (
                "Gross Margin Analysis: "
                "Margin = (SUM(price) - SUM(freight_value)) / SUM(price). "
                "Lower margin = higher freight relative to product price. "
                "Key dimensions: by state (further states have higher freight), "
                "by product category (heavy items cost more to ship), "
                "by seller (some sellers subsidize shipping). "
                "Chart: scatter plot of price vs freight, grouped bar of margin by state."
            ),
        }
        count = 0
        for id_, doc in entries.items():
            self.collection.upsert(
                ids=[id_],
                documents=[doc],
                metadatas=[{"type": "analytics_framework"}],
            )
            count += 1
        return count

    def search(self, query: str, n: int = 3) -> list[dict]:
        """Search for relevant analysis frameworks."""
        results = self.collection.query(query_texts=[query], n_results=n)
        formatted = []
        if results.get("ids") and results["ids"][0]:
            for i, rid in enumerate(results["ids"][0]):
                formatted.append({
                    "id": rid,
                    "document": (results.get("documents") or [[""]])[0][i] if results.get("documents") else "",
                    "metadata": (results.get("metadatas") or [{}])[0][i] if results.get("metadatas") else {},
                })
        return formatted
