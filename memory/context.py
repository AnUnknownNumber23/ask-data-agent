"""Context window manager for LLM token budget control."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnSummary:
    question: str
    answer_brief: str
    tables_used: list[str] = field(default_factory=list)


class ContextWindow:
    """Manages token budget for LLM context window."""

    def __init__(
        self,
        max_turns: int = 10,
        max_tokens: int = 8000,
        max_result_rows: int = 100,
        chars_per_token: float = 3.5,
    ):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.max_result_rows = max_result_rows
        self.chars_per_token = chars_per_token
        self._turns: list[dict[str, str]] = []

    def add_turn(self, question: str, answer: str) -> None:
        self._turns.append({"question": question, "answer": answer})

    def needs_summarization(self) -> bool:
        return len(self._turns) > self.max_turns

    def summarize_early_turns(self) -> str:
        """Compress early conversation turns into a summary string."""
        if not self.needs_summarization():
            return ""

        split_idx = len(self._turns) - self.max_turns
        early = self._turns[:split_idx]
        self._turns = self._turns[split_idx:]

        lines = ["Earlier conversation summary:"]
        for i, turn in enumerate(early):
            q_brief = turn["question"][:80]
            a_brief = turn["answer"][:120]
            lines.append(f"  [{i+1}] Q: {q_brief}... → A: {a_brief}...")

        return "\n".join(lines)

    def prepare_result_context(self, result: Any) -> str:
        """Truncate large query results to a compact summary."""
        if not hasattr(result, "rows"):
            return str(result)

        total_rows = len(result.rows)
        if total_rows <= self.max_result_rows:
            return self._format_full_result(result)

        preview = result.rows[: self.max_result_rows]
        summary = (
            f"[Result truncated: showing {self.max_result_rows} of {total_rows} rows]\n"
            f"Columns: {', '.join(result.columns)}\n"
            f"Preview ({self.max_result_rows} rows):\n"
        )
        summary += self._rows_to_table(result.columns, preview)
        return summary

    def _format_full_result(self, result: Any) -> str:
        header = f"Columns: {', '.join(result.columns)}\nRows ({result.total_returned}):\n"
        return header + self._rows_to_table(result.columns, result.rows)

    def _rows_to_table(self, columns: list[str], rows: list[tuple]) -> str:
        lines = ["| " + " | ".join(columns) + " |"]
        lines.append("|" + "|".join("---" for _ in columns) + "|")
        for row in rows:
            lines.append("| " + " | ".join(str(v)[:50] for v in row) + " |")
        return "\n".join(lines)

    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / self.chars_per_token))

    def is_within_budget(self, text: str) -> bool:
        return self.estimate_tokens(text) <= self.max_tokens
