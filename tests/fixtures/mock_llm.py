"""Mock LLM provider for dev mode — returns realistic responses for Olist dataset."""
import json
from connectors.llm.base import BaseLLMProvider, ChatResponse, Message
from typing import AsyncIterator


class MockLLM(BaseLLMProvider):
    """Returns predetermined responses so the UI works without a real API key."""

    def __init__(self):
        super().__init__(model="mock", api_base="", api_key="")

    async def chat(self, messages: list[Message], **kwargs) -> ChatResponse:
        last = messages[-1].content if messages else ""

        if "Return your analysis" in last or "intent" in last.lower():
            return ChatResponse(content=json.dumps({
                "matched_tables": ["orders", "customers", "order_items", "products"],
                "business_terms": {"GMV": "SUM(price)", "orders": "COUNT(order_id)"},
                "confidence": 0.9,
                "needs_clarification": False,
            }), model="mock")

        if "SQL" in last or "sql" in last.lower():
            return ChatResponse(content=json.dumps({
                "sql": "SELECT c.customer_state, COUNT(*) as order_count FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE o.order_purchase_timestamp >= '2017-01-01' GROUP BY c.customer_state ORDER BY order_count DESC LIMIT 10"
            }), model="mock")

        if "Fix the SQL" in last:
            return ChatResponse(content=json.dumps({
                "sql": "SELECT c.customer_state, COUNT(*) as cnt FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.customer_state ORDER BY cnt DESC LIMIT 10"
            }), model="mock")

        if "insight" in last.lower() or "chart" in last.lower():
            return ChatResponse(content=json.dumps({
                "insight": "São Paulo (SP) leads with the highest order volume, accounting for approximately 42% of all orders. Rio de Janeiro (RJ) and Minas Gerais (MG) follow as the second and third largest markets. This distribution aligns with Brazil's population concentration in the Southeast region.",
                "chart": {
                    "chart_type": "bar",
                    "x": ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE"],
                    "series": [{"name": "Orders", "data": [41700, 12800, 11600, 7200, 6800, 5100, 4200, 3800, 3400, 2800]}]
                }
            }), model="mock")

        return ChatResponse(content=json.dumps({"sql": "SELECT 1 LIMIT 1"}), model="mock")

    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        response = await self.chat(messages, **kwargs)
        for char in response.content:
            yield char
