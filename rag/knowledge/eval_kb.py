"""Eval Knowledge Base — stores evaluator results for quality tracking and trend analysis."""
import time
import chromadb
from rag.embedding import get_embedding_function


class EvalKB:
    """Persistent store for evaluator results. Enables quality trend analysis."""

    def __init__(self, chroma_path: str):
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="eval_kb",
            metadata={"description": "Evaluation results and quality metrics"},
            embedding_function=get_embedding_function(),
        )

    def record(self, session_id: str, gate: int, score: float, verdict: str,
               user_query: str, duration_ms: float, reasoning: str = "") -> str:
        """Record an evaluator gate result. Returns the record ID."""
        ts = int(time.time())
        rid = f"eval:{session_id}:gate{gate}:{ts}"
        doc = f"Gate {gate}: {verdict} (score={score:.2f}) for '{user_query[:100]}'"
        self.collection.upsert(
            ids=[rid],
            documents=[doc],
            metadatas=[{
                "gate": gate,
                "score": score,
                "verdict": verdict,
                "query": user_query[:200],
                "duration_ms": duration_ms,
                "reasoning": reasoning[:200] if reasoning else "",
                "timestamp": ts,
            }],
        )
        return rid

    def stats(self, limit: int = 100) -> dict:
        """Compute quality statistics from recent evaluation records."""
        data = self.collection.get()
        if not data["ids"]:
            return self._empty_stats()

        metas = data.get("metadatas", []) or []
        total = len(metas)

        gate_stats = {}
        for m in metas[-limit:]:
            g = m.get("gate", 0)
            if g not in gate_stats:
                gate_stats[g] = {"total": 0, "pass": 0, "warn": 0, "reject": 0, "scores": []}
            gs = gate_stats[g]
            gs["total"] += 1
            v = m.get("verdict", "")
            if v in ("pass", "warn", "reject"):
                gs[v] += 1
            gs["scores"].append(m.get("score", 0))

        gates = []
        for gid in sorted(gate_stats):
            gs = gate_stats[gid]
            scores = gs["scores"]
            gates.append({
                "gate": gid,
                "total": gs["total"],
                "pass_rate": gs["pass"] / gs["total"] if gs["total"] else 0,
                "warn_rate": gs["warn"] / gs["total"] if gs["total"] else 0,
                "reject_rate": gs["reject"] / gs["total"] if gs["total"] else 0,
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "min_score": min(scores) if scores else 0,
            })

        return {
            "total_evaluations": total,
            "gates": gates,
            "overall_pass_rate": sum(1 for m in metas[-limit:] if m.get("verdict") == "pass") / min(total, limit) if total else 0,
        }

    def recent(self, n: int = 10) -> list[dict]:
        """Get most recent evaluation records."""
        data = self.collection.get()
        if not data["ids"]:
            return []
        records = []
        for i, rid in enumerate(data["ids"]):
            records.append({
                "id": rid,
                "document": (data.get("documents") or [""])[i],
                "metadata": (data.get("metadatas") or [{}])[i],
            })
        records.sort(key=lambda r: r["metadata"].get("timestamp", 0), reverse=True)
        return records[:n]

    def _empty_stats(self) -> dict:
        return {"total_evaluations": 0, "gates": [], "overall_pass_rate": 0}
