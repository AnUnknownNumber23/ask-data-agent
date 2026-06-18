"""Cross-cutting Thinking Tracer — records every agent step I/O for real-time frontend display."""
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class StepRecord:
    step: str
    status: str  # "ok" | "warning" | "error"
    duration_ms: float
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class TraceRecord:
    trace_id: str
    session_id: str
    user_query: str
    steps: list[StepRecord] = field(default_factory=list)
    evaluator_results: list[dict] = field(default_factory=list)
    total_duration_ms: float = 0.0
    total_tokens: dict[str, int] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ThinkingTracer:
    """Cross-cutting tracer — records every agent step I/O for real-time frontend display."""

    def __init__(self, websocket_sender: Callable | None = None):
        self._ws_sender = websocket_sender
        self._current: TraceRecord | None = None
        self._step_timer: float = 0.0

    def start(self, session_id: str, user_query: str) -> TraceRecord:
        self._current = TraceRecord(
            trace_id=f"tr_{int(time.time() * 1000)}",
            session_id=session_id,
            user_query=user_query,
        )
        self._current.started_at = datetime.now(timezone.utc).isoformat()
        return self._current

    def record_step_start(self, step_name: str) -> None:
        self._step_timer = time.perf_counter()

    def record_step_end(self, step_name: str, output: dict[str, Any],
                        status: str = "ok", error: str | None = None) -> None:
        if self._current is None:
            return
        duration_ms = (time.perf_counter() - self._step_timer) * 1000
        step = StepRecord(
            step=step_name,
            status=status,
            duration_ms=round(duration_ms, 2),
            output=output,
            error=error,
        )
        self._current.steps.append(step)
        self._push_to_ws()

    def record_evaluator(self, gate: int, score: float, verdict: str) -> None:
        if self._current is None:
            return
        self._current.evaluator_results.append({
            "gate": gate,
            "score": round(score, 3),
            "verdict": verdict,
        })
        self._push_to_ws()

    def finalize(self, tokens: dict[str, int]) -> TraceRecord:
        if self._current is None:
            raise RuntimeError("No active trace")
        self._current.total_tokens = tokens
        total_ms = sum(s.duration_ms for s in self._current.steps)
        self._current.total_duration_ms = round(total_ms, 2)
        self._push_to_ws()
        return self._current

    def _push_to_ws(self) -> None:
        if self._ws_sender and self._current:
            import asyncio
            data = self.to_dict()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._ws_sender(data))
            except RuntimeError:
                pass

    def to_dict(self) -> dict[str, Any]:
        if self._current is None:
            return {}
        return {
            "trace_id": self._current.trace_id,
            "session_id": self._current.session_id,
            "user_query": self._current.user_query,
            "steps": [
                {
                    "step": s.step,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "output": s.output,
                    "error": s.error,
                }
                for s in self._current.steps
            ],
            "evaluator_results": self._current.evaluator_results,
            "total_duration_ms": self._current.total_duration_ms,
            "total_tokens": self._current.total_tokens,
        }
