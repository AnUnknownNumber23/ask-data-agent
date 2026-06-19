import re
from typing import Any

from .base import BaseRetrieveStrategy, RAGResult


class ExactCorrectionStrategy(BaseRetrieveStrategy):
    """REFLECT stage: exact + fuzzy field name matching. VECTOR WEIGHT = 0."""

    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        error_msg = context.get("error_message", "")
        quoted = re.findall(r"'([^']*)'", error_msg)
        corrections = {}
        # 1. Check Fix KB for known error patterns
        if "fix_kb" in self.kbs:
            for name in quoted:
                fixes = self.kbs["fix_kb"].lookup(name)
                if fixes:
                    for rid, doc in fixes.items():
                        # Parse fix: "Use X instead" or "→ X"
                        corrections[name] = doc[:80]
        # 2. Schema KB: exact + fuzzy column lookup
        if "schema_kb" in self.kbs:
            for name in quoted:
                if name not in corrections:
                    exact = self.kbs["schema_kb"].exact_column_lookup(name)
                    if not exact:
                        fuzzy = self.kbs["schema_kb"].search_columns(name, n=3)
                        if fuzzy:
                            corrections[name] = fuzzy[0]["metadata"].get("name", name)
        # 3. Also try keyword search on columns for better matching
            for name in quoted:
                if name not in corrections:
                    kw = self.kbs["schema_kb"].keyword_search_columns(name, n=3)
                    if kw:
                        corrections[name] = kw[0]["metadata"].get("name", name)
        return RAGResult(
            matches=[{"corrections": corrections}],
            strategy_name="exact_correction",
            confidence=0.9 if corrections else 0.0,
        )
