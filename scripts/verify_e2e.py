"""End-to-end verification using a mock LLM."""
import asyncio
import sys
sys.path.insert(0, '.')

from connectors.dw.duckdb import DuckDBConnector
from connectors.llm.base import Message, ChatResponse
from evaluator.rules import SQLEvaluator
from monitoring.tracer import ThinkingTracer
from agent.graph import build_agent_graph
from agent.state import AgentState
from prompts.manager import PromptManager


class MockLLM:
    async def chat(self, messages: list[Message], **kwargs) -> ChatResponse:
        import json
        last = messages[-1].content if messages else ""

        if "Return your analysis" in last or "intent" in last.lower():
            return ChatResponse(content=json.dumps({
                "matched_tables": ["orders", "customers"],
                "business_terms": {"orders": "order count"},
                "confidence": 0.9,
                "needs_clarification": False,
            }), model="mock")

        if "SQL" in last or "sql" in last.lower():
            return ChatResponse(content=json.dumps({
                "sql": "SELECT c.customer_state, count(*) as cnt FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.customer_state ORDER BY cnt DESC LIMIT 10"
            }), model="mock")

        if "Fix the SQL" in last:
            return ChatResponse(content=json.dumps({
                "sql": "SELECT c.customer_state, count(*) as cnt FROM orders o JOIN customers c ON o.customer_id = c.customer_id GROUP BY c.customer_state ORDER BY cnt DESC LIMIT 10"
            }), model="mock")

        if "insight" in last.lower() or "chart" in last.lower():
            return ChatResponse(content=json.dumps({
                "insight": "The top state is SP with the most orders, followed by RJ and MG. This aligns with population distribution in Brazil.",
                "chart": {"chart_type": "bar", "x": ["SP","RJ","MG","RS","PR"], "series": [{"name": "orders", "data": [42000,15000,12000,8000,7000]}]}
            }), model="mock")

        return ChatResponse(content=json.dumps({"sql": "SELECT 1 LIMIT 1"}), model="mock")


async def main():
    print("=== ask-data-agent E2E Verification ===\n")

    # 1. Test DW connectivity
    print("[1/4] Testing DW connector...")
    dw = DuckDBConnector("data/olist.duckdb")
    tables = await dw.list_tables()
    assert len(tables) >= 9, f"Expected 9+ tables, got {len(tables)}"
    print(f"  OK: {len(tables)} tables found")

    # 2. Test SQL rule engine
    print("[2/4] Testing SQL evaluator...")
    evaluator = SQLEvaluator()
    result = evaluator.check("SELECT * FROM orders LIMIT 10")
    assert result.verdict.value == "pass", f"Expected pass, got {result.verdict.value}"
    result = evaluator.check("DROP TABLE orders")
    assert result.verdict.value == "reject", f"Expected reject, got {result.verdict.value}"
    print("  OK: rule engine correctly passes/rejects")

    # 3. Test agent graph with mock LLM
    print("[3/4] Testing agent graph (mock LLM)...")
    llm = MockLLM()
    tracer = ThinkingTracer()

    # Minimal RAG mock
    class MockRAG:
        async def retrieve(self, stage, query, context):
            from rag.strategies.base import RAGResult
            return RAGResult(matches=[{"document": "orders table with order_id, customer_id", "id": "t1"}], strategy_name="mock", confidence=0.9)

    rag = MockRAG()
    prompts = PromptManager(
        template_dir="prompts/templates",
        config_path="prompts/config/prompt_config.yaml",
    )
    graph = build_agent_graph(llm, dw, rag, prompts, tracer, evaluator)

    tracer.start("e2e_test", "How many orders per state?")
    initial_state: AgentState = {
        "messages": [], "session_id": "e2e_test", "user_query": "How many orders per state?",
        "intent": {}, "matched_tables": [], "business_terms": {},
        "generated_sql": "", "sql_error": None, "retry_count": 0,
        "query_result": None, "result_summary": "",
        "analysis_text": "", "chart_config": None, "evaluator_results": [],
        "clarification_question": None, "degradation_message": None, "escalation_ticket": None,
        "is_report_mode": False, "report_outline": None, "report_sections": [],
    }

    result = await graph.ainvoke(initial_state)
    print(f"  Analysis: {result.get('analysis_text', 'N/A')[:100]}...")
    print(f"  Chart: {result.get('chart_config', {}).get('chart_type', 'N/A')}")
    print(f"  Steps: {len(tracer.to_dict().get('steps', []))}")

    # 4. Verify trace is complete
    print("[4/4] Verifying trace...")
    trace = tracer.to_dict()
    steps = trace.get("steps", [])
    step_names = [s["step"] for s in steps]
    print(f"  Steps executed: {step_names}")
    assert len(steps) >= 4, f"Expected 4+ steps, got {len(steps)}"

    print("\n=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
