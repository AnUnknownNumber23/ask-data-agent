"""Gate 3: Output Evaluator — hallucination detection and quality check."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def output_evaluator_gate(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("OUTPUT_EVAL")
    text = state.get("analysis_text", "")
    result = state.get("query_result", {})
    evaluator_results = list(state.get("evaluator_results", []))

    # Simple hard check: extract numbers from text, verify they appear in results
    warnings = []
    if result and result.get("rows"):
        import re
        numbers_in_text = set(re.findall(r'\b(\d+(?:\.\d+)?)\b', text))
        numbers_in_data = set()
        for row in result["rows"]:
            for val in row:
                numbers_in_data.add(str(val))
        extras = numbers_in_text - numbers_in_data
        if extras:
            warnings.append(f"Potential hallucination: numbers not in data: {extras}")

    verdict = "pass" if not warnings else "warn"
    entry = {"gate": 3, "verdict": verdict, "warnings": warnings}
    evaluator_results.append(entry)
    tracer.record_evaluator(3, 0.8 if verdict == "pass" else 0.4, verdict)
    tracer.record_step_end("OUTPUT_EVAL", entry)
    return {"evaluator_results": evaluator_results}
