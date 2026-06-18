from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class ContextSupplementStrategy(BaseRetrieveStrategy):
    """REASON stage: get JOIN relationships, field types, indexes for matched tables."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        results = []
        matched = context.get("matched_tables", [])
        if "schema_kb" in self.kbs:
            for table in matched:
                cols = self.kbs["schema_kb"].search_columns("", table=table, n=self.top_k)
                results.extend(cols)
        return RAGResult(matches=results, strategy_name="context_supplement", confidence=0.9)
