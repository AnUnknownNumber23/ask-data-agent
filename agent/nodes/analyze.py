"""ANALYZE node — interpret query results and generate insights + chart config."""
import json
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


async def analyze_node(
    state: AgentState, llm: BaseLLMProvider, rag: RAGRouter,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("ANALYZE")
    result = state.get("query_result", {})
    if not result or not result.get("rows"):
        return {"analysis_text": "No data found for your query.", "chart_config": None}

    rag_result = await rag.retrieve(Stage.ANALYZE, state["user_query"], context={
        "result_summary": _summarize(result),
    })

    prompt_text = prompts.render("analyze.j2", {
        "user_query": state["user_query"],
        "query_result_summary": _summarize(result),
        "analytics_framework": str(rag_result.matches),
    })

    response = await llm.chat([
        Message(role="system", content="You are a data analyst. Return JSON with 'insight' and 'chart' fields."),
        Message(role="user", content=prompt_text),
    ])

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {"insight": response.content[:500], "chart": _default_chart(result)}

    tracer.record_step_end("ANALYZE", {"has_chart": data.get("chart") is not None})
    return {"analysis_text": data.get("insight", ""), "chart_config": data.get("chart")}


def _summarize(result: dict) -> str:
    cols = result.get("columns", [])
    rows = result.get("rows", [])
    return f"Columns: {cols}\nRows: {rows[:5]}"


def _default_chart(result: dict) -> dict | None:
    cols = result.get("columns", [])
    rows = result.get("rows", [])
    if len(cols) >= 2 and rows:
        return {"chart_type": "bar", "x": [str(r[0]) for r in rows[:20]],
                "series": [{"name": cols[1], "data": [r[1] for r in rows[:20]]}]}
    return None
