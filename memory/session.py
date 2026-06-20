"""Session memory — multi-turn conversation history, file-backed in dev, Redis in prod."""
import json
import os
import time
from pathlib import Path
from typing import Any


class SessionStore:
    """Stores conversation history per session. File-based (JSON) for dev, Redis for prod."""

    def __init__(self, storage_dir: str = "./data/sessions", max_turns: int = 10,
                 ttl_seconds: int = 3600):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self._redis = None
        # Try Redis if available
        try:
            import redis
            r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
            r.ping()
            self._redis = r
        except Exception:
            pass

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get recent conversation turns for a session."""
        if self._redis:
            data = self._redis.get(f"session:{session_id}")
            return json.loads(data) if data else []
        return self._read_file(session_id)

    def add_turn(self, session_id: str, user_query: str, answer: str,
                 matched_tables: list[str], generated_sql: str) -> None:
        """Record a completed Q&A turn."""
        history = self.get_history(session_id)

        turn = {
            "query": user_query,
            "answer": answer[:500],
            "matched_tables": matched_tables,
            "sql": generated_sql[:300],
            "timestamp": int(time.time()),
        }
        history.append(turn)

        # Trim old turns
        if len(history) > self.max_turns:
            history = history[-self.max_turns:]

        if self._redis:
            self._redis.setex(
                f"session:{session_id}",
                self.ttl_seconds,
                json.dumps(history, ensure_ascii=False),
            )
        else:
            self._write_file(session_id, history)

    def format_for_prompt(self, session_id: str) -> str:
        """Format recent history as a string for the LLM prompt."""
        history = self.get_history(session_id)
        if not history:
            return ""
        lines = []
        for i, turn in enumerate(history[-5:], 1):  # Last 5 turns
            lines.append(f"Q{i}: {turn['query']}")
            # Truncate answer at the first analysis marker (归因/预测/异常)
            answer = turn['answer']
            for marker in ["\n\n---", "归因分析", "趋势预测", "异常预警"]:
                idx = answer.find(marker)
                if idx > 0:
                    answer = answer[:idx]
                    break
            lines.append(f"A{i}: {answer[:200]}")
            if turn.get("matched_tables"):
                lines.append(f"Tables{i}: {', '.join(turn['matched_tables'])}")
            if turn.get("sql"):
                lines.append(f"SQL{i}: {turn['sql']}")
        # Add instruction to preserve context
        if history:
            last = history[-1]
            if last.get("matched_tables"):
                lines.append(f"IMPORTANT: The previous query used tables: {', '.join(last['matched_tables'])}. If this is a follow-up, reuse these tables.")
        return "\n".join(lines)

    def clear(self, session_id: str) -> None:
        """Delete a session's history."""
        if self._redis:
            self._redis.delete(f"session:{session_id}")
        else:
            path = self._file_path(session_id)
            if path.exists():
                path.unlink()

    def _file_path(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self.storage_dir / f"{safe}.json"

    def _read_file(self, session_id: str) -> list[dict]:
        path = self._file_path(session_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Remove expired sessions
            if data:
                newest = max(t.get("timestamp", 0) for t in data)
                if time.time() - newest > self.ttl_seconds:
                    path.unlink()
                    return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    def _write_file(self, session_id: str, history: list[dict]) -> None:
        self._file_path(session_id).write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# Module-level singleton
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
