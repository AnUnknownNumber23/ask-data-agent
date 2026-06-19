from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class SemanticDiscoveryStrategy(BaseRetrieveStrategy):
    """UNDERSTAND stage: broad semantic search for relevant tables/fields.

    Searches both Schema KB (table/column names) and Business KB (metrics, terms,
    regional definitions). This enables Chinese queries like "东南区毛利率" to match
    the relevant tables even when the query uses business terminology instead of
    actual table names.
    """

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        results = []
        biz_terms = []

        # 1. Search Schema KB for matching tables/columns
        if "schema_kb" in self.kbs:
            tables = self.kbs["schema_kb"].search_tables(query, n=self.top_k)
            filtered = [t for t in tables if t.get("distance", 1.0) <= (self.threshold or 1.0)]
            results.extend(filtered)

            # Fallback: keyword match on table/column names
            if not results:
                kw_tables = self.kbs["schema_kb"].keyword_search_tables(query, n=self.top_k)
                results.extend(kw_tables)
                # Also search column names for keyword matches
                if not results:
                    kw_cols = self.kbs["schema_kb"].keyword_search_columns(query, n=self.top_k)
                    results.extend(kw_cols)

        # 2. Search Business KB for matching business terms (supports Chinese queries)
        if "business_kb" in self.kbs:
            biz_terms = self.kbs["business_kb"].search_terms(query, n=3)
            # Append business term results so the understand node has both
            # schema context AND business context
            results.extend(biz_terms)

        confidence = 1.0 - results[0]["distance"] if results else 0.0
        return RAGResult(matches=results, strategy_name="semantic_discovery", confidence=confidence)
