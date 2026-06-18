"""ESCALATE node — L3: escalate to human analyst."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def escalate_node(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("ESCALATE")
    ticket = {
        "session_id": state.get("session_id"),
        "user_query": state.get("user_query"),
        "attempts": state.get("retry_count", 0),
        "last_sql": state.get("generated_sql"),
        "last_error": state.get("sql_error"),
    }
    tracer.record_step_end("ESCALATE", {"ticket": ticket})
    return {"escalation_ticket": ticket}
