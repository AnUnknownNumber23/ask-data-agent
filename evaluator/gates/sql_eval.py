"""Gate 1: SQL Evaluator — combines rule engine with LLM judge."""
from agent.state import AgentState
from evaluator.rules import SQLEvaluator, Verdict as RuleVerdict
from evaluator.judge import LLMJudge
from monitoring.tracer import ThinkingTracer


async def sql_evaluator_gate(state: AgentState, rule_engine: SQLEvaluator,
                             llm_judge: LLMJudge, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("SQL_EVAL")
    sql = state.get("generated_sql", "")
    user_query = state.get("user_query", "")
    matched_tables = state.get("matched_tables", [])

    # Rule engine (fast, deterministic)
    rule_result = rule_engine.check(sql)

    # LLM judge (semantic match with user intent)
    if sql and rule_result.verdict in (RuleVerdict.PASS, RuleVerdict.WARN):
        jv = await llm_judge.judge_sql(sql, user_query, matched_tables)
    else:
        jv = None

    if rule_result.verdict == RuleVerdict.REJECT:
        verdict = "reject"
        score = 0.0
    elif jv and jv.score < 0.6:
        verdict = "reject"
        score = jv.score
    elif jv and jv.score < 0.8:
        verdict = "warn"
        score = jv.score
    else:
        verdict = "pass"
        score = jv.score if jv else 1.0

    evaluator_results = list(state.get("evaluator_results", []))
    entry = {
        "gate": 1,
        "verdict": verdict,
        "score": score,
        "rule_checks": rule_result.checks,
        "warnings": rule_result.warnings,
        "errors": rule_result.errors,
        "judge_reasoning": jv.reasoning if jv else None,
    }
    evaluator_results.append(entry)
    tracer.record_evaluator(1, score, verdict)
    tracer.record_step_end("SQL_EVAL", entry)
    return {"evaluator_results": evaluator_results}
