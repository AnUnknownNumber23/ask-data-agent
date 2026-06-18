"""REASON node — generate SQL from intent + table schema."""
import json
import re
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


async def reason_node(
    state: AgentState,
    llm: BaseLLMProvider,
    rag: RAGRouter,
    prompts: PromptManager,
    tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("REASON")

    rag_result = await rag.retrieve(Stage.REASON, state["user_query"], context={
        "matched_tables": state.get("matched_tables", []),
    })

    schema_detail = "\n".join(m.get("document", "") for m in rag_result.matches)
    prompt_text = prompts.render("reason.j2", {
        "user_query": state["user_query"],
        "matched_tables": state.get("matched_tables", []),
        "schema_detail": schema_detail,
        "business_rules": state.get("business_terms", {}),
    })

    response = await llm.chat([
        Message(role="system", content="You are a SQL expert. Return valid JSON with a 'sql' field."),
        Message(role="user", content=prompt_text),
    ])

    try:
        data = json.loads(response.content)
        sql = data.get("sql", "")
    except json.JSONDecodeError:
        sql = _extract_sql(response.content)

    tracer.record_step_end("REASON", {"sql": sql[:500]})
    return {"generated_sql": sql}


def _extract_sql(text: str) -> str:
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"(SELECT\b.*?;)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()
