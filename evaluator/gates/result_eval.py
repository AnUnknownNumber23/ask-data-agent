"""Gate 2: Result Evaluator — checks data quality and relevance with LLM judge."""
from agent.state import AgentState
from evaluator.judge import LLMJudge
from monitoring.tracer import ThinkingTracer


async def result_evaluator_gate(state: AgentState, llm_judge: LLMJudge,
                                tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("RESULT_EVAL")
    result = state.get("query_result") or {}
    user_query = state.get("user_query") or ""
    evaluator_results = list(state.get("evaluator_results") or [])

    rows = result.get("rows", [])
    total = result.get("total_returned", 0)
    columns = result.get("columns", [])
    warnings = []

    # Gate 1 already enforces LIMIT 1000, so row count is always <= 1000.
    # The only meaningful check: is the result empty?
    if total == 0:
        verdict = "reflect"
        warnings.append(f"Query returned 0 rows. The user asked: '{user_query[:100]}'. Try removing date filters or checking if the data exists for this time range.")
    else:
        verdict = "pass"

    # LLM judge: is the result relevant to the user's question?
    score = 1.0
    if rows and user_query:
        try:
            jv = await llm_judge.judge_result(user_query, columns, total, rows[:5])
            score = jv.score
            if jv.verdict == "reject" and verdict == "pass":
                verdict = "reflect"
            elif jv.verdict == "warn" and verdict == "pass":
                warnings.append(jv.reasoning)
        except Exception:
            pass

    entry = {"gate": 2, "verdict": verdict, "score": score,
             "row_count": total, "warnings": warnings,
             "suggestion": None}
    evaluator_results.append(entry)

    # Semantic check: did the result actually address the user's question?
    # Ask LLM to verify (lightweight, skipped if Judge is None)
    if llm_judge is not None and rows and user_query:
        from evaluator.judge import LLMJudge
        try:
            jv = await llm_judge.judge_result(user_query, columns, total, rows[:5])
            entry["score"] = jv.score
            if jv.verdict == "reject" and verdict == "pass":
                verdict = "reflect"
                entry["verdict"] = "reflect"
                entry["suggestion"] = jv.reasoning[:200]
            elif jv.verdict == "warn":
                entry["suggestion"] = jv.reasoning[:200]
        except Exception:
            pass  # Judge timeout or error — keep original verdict

    tracer.record_evaluator(2, score, verdict)
    tracer.record_step_end("RESULT_EVAL", entry)

    try:
        from api.dependencies import get_eval_kb
        get_eval_kb().record(
            state.get("session_id", ""), 2, score, verdict,
            user_query, 0, reasoning="",
        )
    except Exception:
        pass

    return {"evaluator_results": evaluator_results}
