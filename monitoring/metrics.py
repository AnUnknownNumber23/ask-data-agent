"""Metrics collector for agent performance tracking."""
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MetricsCollector:
    """Collects and aggregates agent performance metrics."""

    total_requests: int = 0
    total_tokens_used: int = 0
    total_duration_ms: float = 0.0
    evaluator_pass_rates: dict[int, tuple[int, int]] = field(default_factory=dict)
    retry_counts: list[int] = field(default_factory=list)
    errors_by_level: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_request(self, duration_ms: float, tokens: int, retries: int = 0) -> None:
        self.total_requests += 1
        self.total_duration_ms += duration_ms
        self.total_tokens_used += tokens
        self.retry_counts.append(retries)

    def record_evaluator(self, gate: int, passed: bool) -> None:
        prev = self.evaluator_pass_rates.get(gate, (0, 0))
        self.evaluator_pass_rates[gate] = (
            prev[0] + (1 if passed else 0),
            prev[1] + 1,
        )

    def record_error(self, level: str) -> None:
        self.errors_by_level[level] += 1

    def summary(self) -> dict:
        avg_duration = self.total_duration_ms / max(self.total_requests, 1)
        avg_retries = sum(self.retry_counts) / max(len(self.retry_counts), 1)
        gate_rates = {}
        for gate, (passed, total) in self.evaluator_pass_rates.items():
            gate_rates[f"gate_{gate}_pass_rate"] = round(passed / max(total, 1), 3)

        return {
            "total_requests": self.total_requests,
            "avg_duration_ms": round(avg_duration, 1),
            "avg_retries": round(avg_retries, 2),
            "total_tokens": self.total_tokens_used,
            **gate_rates,
            "errors_by_level": dict(self.errors_by_level),
        }
