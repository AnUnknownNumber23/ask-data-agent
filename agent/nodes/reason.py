"""REASON node — generate SQL from intent + table schema."""
import json
import re
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


def _empty_rag_result() -> RAGResult:
    return RAGResult(matches=[], strategy_name="noop", confidence=1.0)


async def reason_node(
    state: AgentState,
    llm: BaseLLMProvider,
    rag: RAGRouter,
    prompts: PromptManager,
    tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("REASON")

    if rag is None:
        rag_result = _empty_rag_result()
    else:
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
    usage = response.usage or {}
    tracer.add_tokens(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    try:
        data = json.loads(response.content)
        sql = data.get("sql", "")
    except json.JSONDecodeError:
        sql = _extract_sql(response.content)

    tracer.record_step_end("REASON", {"sql": sql[:500]})
    return {"generated_sql": sql}


def _extract_sql(text: str) -> str:
    # Try extracting from markdown SQL block
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Try extracting from markdown JSON block (LLM sometimes wraps JSON in ```json)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            data = json.loads(match.group(1))
            if "sql" in data:
                return data["sql"].strip()
        except json.JSONDecodeError:
            pass
    # Try extracting raw SELECT statement
    match = re.search(r"(SELECT\b.*?;)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()
