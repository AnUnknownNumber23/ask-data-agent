"""Unit tests for result_eval and judge — deterministic."""
import pytest
from evaluator.gates.result_eval import result_evaluator_gate
from evaluator.judge import LLMJudge, JudgeVerdict
from monitoring.tracer import ThinkingTracer


class TestResultEvalGate:
    @pytest.mark.asyncio
    async def test_empty_result_triggers_reflect(self):
        state = {"query_result": {"rows": [], "total_returned": 0, "columns": []},
                 "user_query": "test", "evaluator_results": []}
        tracer = ThinkingTracer()
        result = await result_evaluator_gate(state, None, tracer)
        evals = result["evaluator_results"]
        assert evals[-1]["verdict"] == "reflect"

    @pytest.mark.asyncio
    async def test_large_result_triggers_degrade(self):
        state = {"query_result": {"rows": list(range(1000)), "total_returned": 1000, "columns": ["id"]},
                 "user_query": "list all", "evaluator_results": []}
        tracer = ThinkingTracer()
        result = await result_evaluator_gate(state, None, tracer)
        evals = result["evaluator_results"]
        assert evals[-1]["verdict"] == "pass"

    @pytest.mark.asyncio
    async def test_aggregated_query_passes(self):
        state = {"query_result": {"rows": list(range(1000)), "total_returned": 1000, "columns": ["category", "count"]},
                 "user_query": "count orders by category", "evaluator_results": []}
        tracer = ThinkingTracer()
        result = await result_evaluator_gate(state, None, tracer)
        evals = result["evaluator_results"]
        assert evals[-1]["verdict"] == "pass"  # aggregated, not raw list

    @pytest.mark.asyncio
    async def test_normal_result_passes(self):
        state = {"query_result": {"rows": [("a", 1), ("b", 2)], "total_returned": 2, "columns": ["x", "y"]},
                 "user_query": "test", "evaluator_results": []}
        tracer = ThinkingTracer()
        result = await result_evaluator_gate(state, None, tracer)
        evals = result["evaluator_results"]
        assert evals[-1]["verdict"] == "pass"

    @pytest.mark.asyncio
    async def test_no_rows_passes(self):
        """Missing query_result should not crash"""
        state = {"user_query": "test", "evaluator_results": []}
        tracer = ThinkingTracer()
        result = await result_evaluator_gate(state, None, tracer)
        evals = result["evaluator_results"]
        assert evals[-1]["verdict"] == "reflect"  # total_returned = 0 by default


class TestLLMJudge:
    @pytest.mark.asyncio
    async def test_disabled_returns_pass(self):
        from connectors.llm.base import BaseLLMProvider
        class FakeLLM(BaseLLMProvider):
            def __init__(self):
                super().__init__("test", "http://x", "key")
            async def chat(self, messages, **kwargs):
                raise RuntimeError("Should not be called")
            async def stream(self, messages, **kwargs):
                raise RuntimeError("Should not be called")

        judge = LLMJudge(FakeLLM())
        v = await judge.judge_sql("SELECT 1", "count", ["orders"])
        assert v.score == 1.0
        assert v.verdict == "pass"

    @pytest.mark.asyncio
    async def test_judge_output_also_disabled(self):
        from connectors.llm.base import BaseLLMProvider
        class FakeLLM(BaseLLMProvider):
            def __init__(self):
                super().__init__("test", "http://x", "key")
            async def chat(self, messages, **kwargs):
                raise RuntimeError("Should not be called")
            async def stream(self, messages, **kwargs):
                raise RuntimeError("Should not be called")

        judge = LLMJudge(FakeLLM())
        v = await judge.judge_output("text", "query", {"columns": ["a"], "rows": [(1,)]})
        assert v.score == 1.0

    @pytest.mark.asyncio
    async def test_judge_result_also_disabled(self):
        from connectors.llm.base import BaseLLMProvider
        class FakeLLM(BaseLLMProvider):
            def __init__(self):
                super().__init__("test", "http://x", "key")
            async def chat(self, messages, **kwargs):
                raise RuntimeError("Should not be called")
            async def stream(self, messages, **kwargs):
                raise RuntimeError("Should not be called")

        judge = LLMJudge(FakeLLM())
        v = await judge.judge_result("query", ["col"], 5, [(1,)])
        assert v.score == 1.0
