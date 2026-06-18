"""Gate 1: SQL Evaluator — combines rule engine with LLM judge."""
from agent.state import AgentState
from evaluator.rules import SQLEvaluator, Verdict as RuleVerdict
from monitoring.tracer import ThinkingTracer


async def sql_evaluator_gate(state: AgentState, rule_engine: SQLEvaluator, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("SQL_EVAL")
    sql = state.get("generated_sql", "")

    rule_result = rule_engine.check(sql)
    evaluator_results = list(state.get("evaluator_results", []))

    entry = {
        "gate": 1,
        "verdict": rule_result.verdict.value,
        "rule_checks": rule_result.checks,
        "warnings": rule_result.warnings,
        "errors": rule_result.errors,
    }
    evaluator_results.append(entry)
    tracer.record_evaluator(1, 1.0 if rule_result.verdict == RuleVerdict.PASS else 0.0, rule_result.verdict.value)
    tracer.record_step_end("SQL_EVAL", entry)
    return {"evaluator_results": evaluator_results}
