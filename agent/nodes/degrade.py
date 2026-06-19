"""DEGRADE node — L2: provide partial/alternative results with data summary."""
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer


async def degrade_node(state: AgentState, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("DEGRADE")
    result = state.get("query_result", {}) or {}
    rows = result.get("rows", [])
    cols = result.get("columns", [])
    total = len(rows)

    msg = (state.get("degradation_message")
           or f"数据量较大，仅返回前 {total} 行（已达上限）。")

    # Include a quick data summary
    if cols and rows:
        preview = ", ".join(str(r[0]) for r in rows[:5])
        msg += f"\n字段：{', '.join(cols[:8])}。"
        msg += f"\n前 5 行示例：{preview}。"

    # Build a summary for ANALYZE to work with
    summary = state.get("result_summary") or ""
    if cols and rows:
        summary = f"Columns: {cols}\nRows (first 100): {rows[:100]}"
    elif cols:
        summary = f"Columns: {cols}\nRows: {rows}"

    tracer.record_step_end("DEGRADE", {"message": msg})
    return {
        "degradation_message": msg,
        "result_summary": summary,
    }
