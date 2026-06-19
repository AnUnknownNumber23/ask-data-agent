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

    # Rule checks
    if total == 0:
        verdict = "reflect"
    elif total >= 1000:
        # Degrade only if result is raw list of IDs (not aggregated)
        # Aggregated results (e.g., GROUP BY categories) with 1000 rows is fine
        is_aggregated = any(
            kw in user_query.lower()
            for kw in ["count", "sum", "avg", "group", "trend", "average", "total", "统计", "总计", "平均", "趋势", "排名", "占比", "分布"]
        ) or any(
            kw in str(columns).lower()
            for kw in ["count", "sum", "avg", "total", "sales", "order_count", "统计", "数量"]
        )
        if is_aggregated:
            verdict = "pass"
        else:
            verdict = "degrade"
            warnings.append("Raw list of records at LIMIT boundary — suggest aggregating or filtering")
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
             "row_count": total, "warnings": warnings}
    evaluator_results.append(entry)
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
