"""Integration tests for full agent graph — mock LLM, real DW + RAG."""
import os
import pytest
from pathlib import Path

# Load .env before imports
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

from tests.fixtures.mock_llm import MockLLM
from connectors.dw.duckdb import DuckDBConnector
from prompts.manager import PromptManager
from evaluator.rules import SQLEvaluator
from agent.graph import build_agent_graph
from monitoring.tracer import ThinkingTracer


@pytest.fixture(scope="module")
def llm():
    return MockLLM()


@pytest.fixture(scope="module")
def dw():
    return DuckDBConnector(str(Path(__file__).parent.parent.parent / "data" / "olist.duckdb"))


@pytest.fixture(scope="module")
def prompts():
    base = Path(__file__).parent.parent.parent
    return PromptManager(
        template_dir=str(base / "prompts" / "templates"),
        config_path=str(base / "prompts" / "config" / "prompt_config.yaml"),
    )


@pytest.fixture(scope="module")
def sql_evaluator():
    return SQLEvaluator(max_limit=10000)


@pytest.fixture(scope="module")
async def rag():
    from api.dependencies import get_rag
    return await get_rag()


class TestAgentFullPipeline:
    """Full pipeline tests — mock LLM avoids API calls, real DW + RAG."""

    @pytest.mark.asyncio
    async def test_basic_query_returns_all_steps(self, llm, dw, prompts, sql_evaluator, rag):
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("how many orders per state")
        result = await graph.ainvoke(state)

        sql = result.get("generated_sql", "")
        tables = result.get("matched_tables", [])
        assert sql, "Should generate SQL"
        assert len(tables) > 0, "Should match tables"

    @pytest.mark.asyncio
    async def test_query_returns_analysis_text(self, llm, dw, prompts, sql_evaluator, rag):
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("top 5 product categories")
        result = await graph.ainvoke(state)

        answer = result.get("analysis_text", "")
        assert answer, "Should return analysis text"
        assert "São Paulo" in answer or "SP" in answer, "Mock LLM should return SP data"

    @pytest.mark.asyncio
    async def test_sql_is_select_only(self, llm, dw, prompts, sql_evaluator, rag):
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("count orders")
        result = await graph.ainvoke(state)

        sql = result.get("generated_sql", "").upper()
        assert sql.startswith("SELECT"), f"SQL must be SELECT: {sql[:50]}"
        assert "DROP" not in sql and "DELETE" not in sql, "No dangerous operations"

    @pytest.mark.asyncio
    async def test_sql_executes_successfully(self, llm, dw, prompts, sql_evaluator, rag):
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("how many orders")
        result = await graph.ainvoke(state)

        query_result = result.get("query_result") or {}
        rows = query_result.get("rows", [])
        assert len(rows) > 0, "SQL must return data"
        assert result.get("sql_error") is None, f"SQL error: {result.get('sql_error')}"

    @pytest.mark.asyncio
    async def test_no_clarify_when_tables_found(self, llm, dw, prompts, sql_evaluator, rag):
        """Mock LLM always returns tables, so should never clarify."""
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("show me orders")
        result = await graph.ainvoke(state)

        assert result.get("clarification_question") is None, "Should NOT ask for clarification"

    @pytest.mark.asyncio
    async def test_escalate_not_triggered(self, llm, dw, prompts, sql_evaluator, rag):
        graph = build_agent_graph(llm, dw, rag, prompts, ThinkingTracer(), sql_evaluator)
        state = self._make_state("valid query")
        result = await graph.ainvoke(state)

        assert result.get("escalation_ticket") is None, "Should NOT escalate"

    def _make_state(self, query: str) -> dict:
        return {
            "messages": [], "session_id": "test", "user_query": query,
            "intent": {}, "matched_tables": [], "business_terms": {},
            "generated_sql": "", "sql_error": None, "retry_count": 0,
            "query_result": None, "result_summary": "",
            "analysis_text": "", "chart_config": None, "evaluator_results": [],
            "clarification_question": None, "degradation_message": None, "escalation_ticket": None,
            "is_report_mode": False, "report_outline": None, "report_sections": [],
        }
