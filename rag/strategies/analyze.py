from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class DomainKnowledgeStrategy(BaseRetrieveStrategy):
    """ANALYZE stage: retrieve analysis frameworks and visualization suggestions."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        return RAGResult(matches=[], strategy_name="domain_knowledge", confidence=0.5)
