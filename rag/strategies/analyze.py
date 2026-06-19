from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class DomainKnowledgeStrategy(BaseRetrieveStrategy):
    """ANALYZE stage: retrieve analysis frameworks and visualization suggestions."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        results = []
        if "analytics_kb" in self.kbs:
            frameworks = self.kbs["analytics_kb"].search(query, n=self.top_k)
            results.extend(frameworks)
        # Also search business KB for metric definitions
        if "business_kb" in self.kbs:
            biz = self.kbs["business_kb"].search_terms(query, n=2)
            results.extend(biz)

        confidence = 0.8 if results else 0.5
        return RAGResult(matches=results, strategy_name="domain_knowledge", confidence=confidence)
