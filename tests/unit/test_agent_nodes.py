"""Unit tests for degrade/clarify/escalate nodes — deterministic, no LLM."""
import pytest
from agent.nodes.degrade import degrade_node
from agent.nodes.clarify import clarify_node
from agent.nodes.escalate import escalate_node
from monitoring.tracer import ThinkingTracer


class TestDegradeNode:
    @pytest.mark.asyncio
    async def test_with_data_returns_summary(self):
        state = {
            "query_result": {
                "columns": ["id", "name", "sales"],
                "rows": [("a", "Alpha", 100), ("b", "Beta", 200), ("c", "Gamma", 300)],
            }
        }
        tracer = ThinkingTracer()
        result = await degrade_node(state, tracer)
        # Check that message contains row count and column names
        msg = result["degradation_message"]
        assert "3" in msg or "three" in msg.lower() or "3" in repr(msg)
        assert "id" in msg
        assert "a" in msg  # first value of first row
        assert "result_summary" in result

    @pytest.mark.asyncio
    async def test_empty_result(self):
        state = {"query_result": {"columns": [], "rows": []}}
        tracer = ThinkingTracer()
        result = await degrade_node(state, tracer)
        assert "0 行" in result["degradation_message"]

    @pytest.mark.asyncio
    async def test_no_query_result(self):
        state = {}
        tracer = ThinkingTracer()
        result = await degrade_node(state, tracer)
        assert "0 行" in result["degradation_message"]

    @pytest.mark.asyncio
    async def test_custom_message_preserved(self):
        state = {"degradation_message": "定制降级消息", "query_result": {"columns": [], "rows": []}}
        tracer = ThinkingTracer()
        result = await degrade_node(state, tracer)
        assert result["degradation_message"] == "定制降级消息"


class TestClarifyNode:
    @pytest.mark.asyncio
    async def test_returns_existing_question(self):
        state = {"clarification_question": "What do you mean?"}
        tracer = ThinkingTracer()
        result = await clarify_node(state, tracer)
        assert result["clarification_question"] == "What do you mean?"

    @pytest.mark.asyncio
    async def test_fallback_when_none(self):
        state = {"clarification_question": None}
        tracer = ThinkingTracer()
        result = await clarify_node(state, tracer)
        assert "无法确定" in result["clarification_question"]

    @pytest.mark.asyncio
    async def test_fallback_when_empty_state(self):
        tracer = ThinkingTracer()
        result = await clarify_node({}, tracer)
        assert "无法确定" in result["clarification_question"]


class TestEscalateNode:
    @pytest.mark.asyncio
    async def test_creates_ticket_and_message(self):
        state = {
            "session_id": "sess_123",
            "user_query": "test query",
            "retry_count": 2,
            "generated_sql": "SELECT * FROM bad",
            "sql_error": "syntax error",
        }
        tracer = ThinkingTracer()
        result = await escalate_node(state, tracer)
        ticket = result["escalation_ticket"]
        assert ticket["session_id"] == "sess_123"
        assert ticket["attempts"] == 2
        assert ticket["last_sql"] == "SELECT * FROM bad"
        assert "转交人工" in result["degradation_message"]
        assert "重试2次" in result["degradation_message"]

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        state = {"session_id": "s", "user_query": "q", "retry_count": 0}
        tracer = ThinkingTracer()
        result = await escalate_node(state, tracer)
        assert "重试0次" in result["degradation_message"]

    @pytest.mark.asyncio
    async def test_missing_fields_handled(self):
        state = {}
        tracer = ThinkingTracer()
        result = await escalate_node(state, tracer)
        ticket = result["escalation_ticket"]
        assert ticket["attempts"] == 0
        assert ticket["last_sql"] is None
