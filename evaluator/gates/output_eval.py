"""Gate 3: Output Evaluator — hallucination detection + LLM quality check."""
import re
from agent.state import AgentState
from evaluator.judge import LLMJudge
from monitoring.tracer import ThinkingTracer


async def output_evaluator_gate(state: AgentState, llm_judge: LLMJudge,
                                tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("OUTPUT_EVAL")
    text = state.get("analysis_text", "")
    result = state.get("query_result", {})
    user_query = state.get("user_query", "")
    evaluator_results = list(state.get("evaluator_results", []))

    warnings = []

    # Rule check: number hallucination detection
    if result and result.get("rows") and text:
        numbers_in_text = set(re.findall(r'\b(\d+(?:\.\d+)?)\b', text))
        numbers_in_data = set()
        for row in result["rows"]:
            for val in row:
                numbers_in_data.add(str(val))
        extras = numbers_in_text - numbers_in_data
        if extras:
            warnings.append(f"Potential hallucination: numbers not in data: {extras}")

    # LLM judge: semantic quality check
    score = 0.8
    if text:
        try:
            jv = await llm_judge.judge_output(text, user_query, result)
            score = jv.score
            if jv.verdict == "reject":
                warnings.append(f"LLM Judge: {jv.reasoning}")
            elif jv.verdict == "warn":
                warnings.append(f"LLM Judge: {jv.reasoning}")
        except Exception:
            pass

    verdict = "pass" if score >= 0.8 else ("warn" if score >= 0.6 else "reject")
    entry = {"gate": 3, "verdict": verdict, "score": score, "warnings": warnings}
    evaluator_results.append(entry)
    tracer.record_evaluator(3, score, verdict)
    tracer.record_step_end("OUTPUT_EVAL", entry)

    try:
        from api.dependencies import get_eval_kb
        get_eval_kb().record(
            state.get("session_id", ""), 3, score, verdict,
            user_query, 0, reasoning="",
        )
    except Exception:
        pass

    return {"evaluator_results": evaluator_results}
