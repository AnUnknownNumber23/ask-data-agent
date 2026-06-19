"""Unit tests for REFLECT node — deterministic function replacement."""
import pytest
from unittest.mock import patch
from agent.nodes.reflect import reflect_node
from monitoring.tracer import ThinkingTracer


class TestReflectFunctionReplacement:
    @pytest.mark.asyncio
    async def test_date_format_replaced(self):
        state = {
            "sql_error": "function date_format does not exist",
            "generated_sql": "SELECT DATE_FORMAT(timestamp, '%Y-%m') FROM orders LIMIT 1000",
            "retry_count": 0,
            "user_query": "use DATE_FORMAT",
            "matched_tables": ["orders"],
            "query_result": {"rows": [], "total_returned": 0},
        }
        tracer = ThinkingTracer()
        result = await reflect_node(state, None, None, None, tracer)

        assert "STRFTIME" in result["generated_sql"]
        assert "DATE_FORMAT" not in result["generated_sql"].upper()
        assert result["retry_count"] == 1
        assert result["sql_error"] is None
        assert "_reflect_guidance" in result

    @pytest.mark.asyncio
    async def test_to_days_replaced(self):
        state = {
            "sql_error": "function to_days does not exist",
            "generated_sql": "SELECT TO_DAYS(end_date) - TO_DAYS(start_date) FROM orders LIMIT 1000",
            "retry_count": 0,
            "user_query": "use TO_DAYS",
            "matched_tables": ["orders"],
            "query_result": {"rows": [], "total_returned": 0},
        }
        tracer = ThinkingTracer()
        result = await reflect_node(state, None, None, None, tracer)

        assert "DATEDIFF" in result["generated_sql"]
        assert "TO_DAYS" not in result["generated_sql"]
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_to_char_replaced(self):
        state = {
            "sql_error": "function to_char does not exist",
            "generated_sql": "SELECT TO_CHAR(timestamp, 'format') FROM orders LIMIT 1000",
            "retry_count": 0,
            "user_query": "use TO_CHAR",
            "matched_tables": ["orders"],
            "query_result": {"rows": [], "total_returned": 0},
        }
        tracer = ThinkingTracer()
        result = await reflect_node(state, None, None, None, tracer)

        assert "STRFTIME" in result["generated_sql"]
        assert "TO_CHAR" not in result["generated_sql"]

    @pytest.mark.asyncio
    async def test_no_known_fix_falls_back(self):
        """Unknown error should not have direct fix applied."""
        state = {
            "sql_error": "some random error",
            "generated_sql": "SELECT xyz_unknown_func() FROM t LIMIT 10",
            "retry_count": 0,
            "user_query": "test",
            "matched_tables": ["t"],
            "query_result": {"rows": [], "total_returned": 0},
        }
        tracer = ThinkingTracer()
        result = await reflect_node(state, None, None, None, tracer)

        # No direct fix applied — passes through to LLM fallback
        assert result["retry_count"] == 1
