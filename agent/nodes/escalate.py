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
    retries = state.get('retry_count', 0)
    query = state.get('user_query', '')
    error = state.get('sql_error', '')
    analysis = state.get('analysis_text', '')

    suggestion = ""
    if "column" in error.lower() or "column" in error:
        suggestion = f"建议：检查字段名是否正确。尝试用更简单的查询，如 'show orders' 或 'count orders'。"
    elif "function" in error.lower() or "does not exist" in error:
        suggestion = f"建议：函数名不兼容。DuckDB 支持 STRFTIME 而非 DATE_FORMAT，DATEDIFF 而非 TO_DAYS。"
    elif "timeout" in error.lower():
        suggestion = f"建议：查询超时。尝试缩小日期范围或减少 JOIN。"
    elif analysis:
        suggestion = f"已尝试 {retries} 次自动修正，数据可能不存在。建议简化查询或更换时间范围。"
    else:
        suggestion = f"已尝试 {retries} 次自动修正。建议换一种问法，如 '每月订单趋势' 或 '各州客户数'。"

    msg = f"已转交人工处理（重试{retries}次后仍失败）。\n{suggestion}\n原始问题：{query}"
    return {"escalation_ticket": ticket, "degradation_message": msg}
