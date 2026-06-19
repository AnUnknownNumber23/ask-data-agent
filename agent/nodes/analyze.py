"""ANALYZE node — interpret query results and generate insights + chart config."""
import json
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


def _empty_rag_result() -> RAGResult:
    return RAGResult(matches=[], strategy_name="noop", confidence=1.0)


async def analyze_node(
    state: AgentState, llm: BaseLLMProvider, rag: RAGRouter,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("ANALYZE")
    result = state.get("query_result", {})
    if not result or not result.get("rows"):
        return {"analysis_text": "No data found for your query.", "chart_config": None}

    if rag is None:
        rag_result = _empty_rag_result()
    else:
        rag_result = await rag.retrieve(Stage.ANALYZE, state["user_query"], context={
            "result_summary": _summarize(result),
        })

    prompt_text = prompts.render("analyze.j2", {
        "user_query": state["user_query"],
        "query_result_summary": _summarize(result),
        "analytics_framework": str(rag_result.matches),
    })

    messages = [
        Message(role="system", content="You are a data analyst. Return JSON with 'insight' and 'chart' fields."),
        Message(role="user", content=prompt_text),
    ]

    # Stream tokens to frontend for real-time display, then parse full response
    full_response = ""
    async for token in llm.stream(messages):
        full_response += token
        tracer.stream_token(token)

    try:
        data = json.loads(full_response)
    except json.JSONDecodeError:
        data = {"insight": full_response[:500]}

    # Chart is always auto-generated from query results (reliable, data-backed)
    chart = _default_chart(result)

    tracer.record_step_end("ANALYZE", {"has_chart": chart is not None})
    return {"analysis_text": data.get("insight", ""), "chart_config": chart}


def _summarize(result: dict) -> str:
    cols = result.get("columns", [])
    rows = result.get("rows", [])
    return f"Columns: {cols}\nRows: {rows[:5]}"


def _default_chart(result: dict) -> dict | None:
    """Auto-generate chart config from query result data."""
    cols = result.get("columns", [])
    rows = result.get("rows", [])
    if len(cols) < 2 or not rows:
        return None
    # Pick chart type based on data patterns
    chart_type = "bar"
    x_vals = [str(r[0])[:30] for r in rows[:20]]
    # Try to use all numeric columns as series (up to 4)
    series_list = []
    for ci in range(1, min(len(cols), 5)):
        data_vals = []
        for r in rows[:20]:
            try:
                data_vals.append(float(r[ci]) if r[ci] is not None else 0)
            except (ValueError, TypeError):
                data_vals.append(0)
        series_list.append({"name": str(cols[ci]), "data": data_vals})
    if not series_list:
        return None
    return {"chart_type": chart_type, "x": x_vals, "series": series_list}
