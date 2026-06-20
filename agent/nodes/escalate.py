"""ESCALATE node — L3: escalate to human analyst."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.escalate")


async def escalate_node(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("ESCALATE")
    _log.warning(f"Escalating after {state.get('retry_count', 0)} retries: {state.get('user_query', '')[:100]}")
    ticket = {
        "session_id": state.get("session_id"),
        "user_query": state.get("user_query"),
        "attempts": state.get("retry_count", 0),
        "last_sql": state.get("generated_sql"),
        "last_error": state.get("sql_error"),
    }
    tracer.record_step_end("ESCALATE", {"ticket": ticket})
    msg = f"已转交人工处理（重试{state.get('retry_count',0)}次后仍失败）。问题：{state.get('user_query','')}"
    return {"escalation_ticket": ticket, "degradation_message": msg}
