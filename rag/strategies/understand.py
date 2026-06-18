from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class SemanticDiscoveryStrategy(BaseRetrieveStrategy):
    """UNDERSTAND stage: broad semantic search for relevant tables/fields."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        results = []
        if "schema_kb" in self.kbs:
            tables = self.kbs["schema_kb"].search_tables(query, n=self.top_k)
            filtered = [t for t in tables if t.get("distance", 1.0) <= (self.threshold or 1.0)]
            results.extend(filtered)
        confidence = 1.0 - results[0]["distance"] if results else 0.0
        return RAGResult(matches=results, strategy_name="semantic_discovery", confidence=confidence)
