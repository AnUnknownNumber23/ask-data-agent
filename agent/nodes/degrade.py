"""DEGRADE node — L2: provide partial/alternative results."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def degrade_node(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("DEGRADE")
    msg = state.get("degradation_message", "I couldn't get complete data, but here's what I found.")
    tracer.record_step_end("DEGRADE", {"message": msg})
    return {"degradation_message": msg}
