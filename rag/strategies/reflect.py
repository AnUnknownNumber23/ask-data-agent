import re
from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class ExactCorrectionStrategy(BaseRetrieveStrategy):
    """REFLECT stage: exact + fuzzy field name matching. VECTOR WEIGHT = 0."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        error_msg = context.get("error_message", "")
        quoted = re.findall(r"'([^']*)'", error_msg)
        corrections = {}
        if "schema_kb" in self.kbs:
            for name in quoted:
                exact = self.kbs["schema_kb"].exact_column_lookup(name)
                if not exact:
                    fuzzy = self.kbs["schema_kb"].search_columns(name, n=3)
                    if fuzzy:
                        corrections[name] = fuzzy[0]["metadata"].get("name", name)
        return RAGResult(
            matches=[{"corrections": corrections}],
            strategy_name="exact_correction",
            confidence=0.9 if corrections else 0.0,
        )
