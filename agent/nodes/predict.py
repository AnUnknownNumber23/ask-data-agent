"""PREDICT node — trend forecasting via LLM pattern reasoning."""
import json
from agent.state import AgentState
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from connectors.dw.base import BaseDWConnector
from monitoring.tracer import ThinkingTracer


async def predict_node(
    state: AgentState, llm: BaseLLMProvider, dw: BaseDWConnector,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("PREDICT")
    user_query = state.get("user_query") or ""
    current_answer = state.get("analysis_text") or ""
    query_result = state.get("query_result") or {}
    current_sql = state.get("generated_sql") or ""

    rows = query_result.get("rows", [])
    cols = query_result.get("columns", [])

    # 1. Ensure we have time series data by extending the existing query
    if not rows or not cols:
        tracer.record_step_end("PREDICT", {"error": "no data"})
        return {"analysis_text": current_answer + "\n\n(数据不足，无法进行预测分析)"}

    # 2. LLM reasons about trends and generates forecast
    data_summary = f"Columns: {cols}\nRows (all data): {rows[:100]}" if len(rows) <= 100 else f"Columns: {cols}\nRows (first 50): {rows[:50]}\nRows (last 50): {rows[-50:]}\nTotal rows: {len(rows)}"

    prompt_text = prompts.render("predict.j2", {
        "user_query": user_query,
        "current_answer": current_answer[:500],
        "current_sql": current_sql[:300],
        "data_summary": data_summary[:3000],
    })

    response = await llm.chat([
        Message(role="system", content="You are a forecasting analyst. Return JSON with 'forecast' and 'confidence' fields in Chinese."),
        Message(role="user", content=prompt_text),
    ])

    try:
        forecast_data = json.loads(response.content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        forecast_data = json.loads(match.group(0)) if match else {}

    forecast_text = forecast_data.get("forecast", response.content[:500])
    confidence = forecast_data.get("confidence", 0.5)

    # 3. Alert check: significant period-over-period changes
    alert_text = ""
    if len(rows) >= 2 and len(cols) >= 2:
        try:
            # Compare last two periods for numeric columns
            last_row = rows[-1]
            prev_row = rows[-2]
            changes = []
            for ci in range(1, min(len(cols), 5)):
                try:
                    curr_val = float(last_row[ci]) if last_row[ci] is not None else 0
                    prev_val = float(prev_row[ci]) if prev_row[ci] is not None else 0
                    if prev_val != 0:
                        pct = ((curr_val - prev_val) / abs(prev_val)) * 100
                        if abs(pct) >= 20:
                            direction = "上升" if pct > 0 else "下降"
                            changes.append(f"{cols[ci]}环比{direction} {abs(pct):.0f}%")
                except (ValueError, TypeError, IndexError):
                    pass
            if changes:
                alert_text = f"\n\n**异常预警：**\n" + "\n".join(f"- {c}" for c in changes)
        except Exception:
            pass

    result_text = (current_answer
                   + f"\n\n---\n**趋势预测：**\n{forecast_text}"
                   + (f"\n(置信度: {confidence:.0%})" if confidence else "")
                   + (alert_text if alert_text else ""))

    tracer.record_step_end("PREDICT", {"has_forecast": bool(forecast_text), "confidence": confidence, "alerts": bool(alert_text)})
    return {"analysis_text": result_text}
