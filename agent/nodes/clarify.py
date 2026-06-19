"""CLARIFY node — L1: ask user for more information."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def clarify_node(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("CLARIFY")
    question = state.get("clarification_question") or "请提供更多信息，我无法确定你想查询什么。"
    tracer.record_step_end("CLARIFY", {"question": question})
    return {"clarification_question": question}
