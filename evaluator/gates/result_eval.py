"""Gate 2: Result Evaluator — checks data quality and relevance."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def result_evaluator_gate(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("RESULT_EVAL")
    result = state.get("query_result", {})
    evaluator_results = list(state.get("evaluator_results", []))

    rows = result.get("rows", [])
    total = result.get("total_returned", 0)
    warnings = []

    if total == 0:
        verdict = "reflect"  # Route to REFLECT to try broader query
    elif len(rows) >= 1000:
        verdict = "degrade"
        warnings.append("Result may be truncated at LIMIT boundary")
    else:
        verdict = "pass"

    entry = {"gate": 2, "verdict": verdict, "row_count": total, "warnings": warnings}
    evaluator_results.append(entry)
    tracer.record_evaluator(2, 1.0 if verdict == "pass" else 0.5, verdict)
    tracer.record_step_end("RESULT_EVAL", entry)
    return {"evaluator_results": evaluator_results}
