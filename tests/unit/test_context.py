import pytest
from memory.context import ContextWindow


class TestContextWindow:
    @pytest.fixture
    def ctx(self):
        return ContextWindow(max_turns=3, max_tokens=8000, max_result_rows=5)

    def test_add_turn(self, ctx):
        ctx.add_turn("What is GMV?", "GMV is total sales.")
        assert len(ctx._turns) == 1

    def test_needs_summarization_when_over_max(self, ctx):
        for i in range(5):
            ctx.add_turn(f"Q{i}", f"A{i}")
        assert ctx.needs_summarization() is True

    def test_needs_summarization_when_under_max(self, ctx):
        ctx.add_turn("Q1", "A1")
        assert ctx.needs_summarization() is False

    def test_summarize_early_turns_keeps_recent(self, ctx):
        for i in range(5):
            ctx.add_turn(f"Q{i}", f"Answer {i}")
        summary = ctx.summarize_early_turns()
        assert "Earlier conversation summary" in summary
        assert len(ctx._turns) == 3  # max_turns kept
        assert ctx._turns[-1]["question"] == "Q4"

    def test_prepare_result_context_small_result(self, ctx):
        from connectors.dw.base import QueryResult
        result = QueryResult(
            columns=["id", "name"],
            rows=[(1, "Alice"), (2, "Bob")],
            total_returned=2,
        )
        output = ctx.prepare_result_context(result)
        assert "Alice" in output
        assert "Bob" in output

    def test_prepare_result_context_large_result_truncates(self, ctx):
        from connectors.dw.base import QueryResult
        result = QueryResult(
            columns=["id"],
            rows=[(i,) for i in range(20)],
            total_returned=20,
        )
        output = ctx.prepare_result_context(result)
        assert "truncated" in output

    def test_estimate_tokens(self, ctx):
        tokens = ctx.estimate_tokens("hello world")
        assert tokens > 0

    def test_is_within_budget(self, ctx):
        assert ctx.is_within_budget("short text") is True
