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

    # If REFLECT already fixed the SQL (direct string replacement), skip LLM and use it directly.
    # The LLM would just regenerate the broken function name from the user query.
    reflect_guidance = state.get("_reflect_guidance") or ""
    if reflect_guidance and state.get("retry_count", 0) > 0:
        # REFLECT already corrected the SQL — pass it through, LLM would only break it again
        corrected_sql = state.get("generated_sql") or ""
        if corrected_sql:
            tracer.record_step_start("REASON")
            tracer.record_step_end("REASON", {"sql": corrected_sql[:500], "source": "reflect_fix"})
            return {"generated_sql": corrected_sql, "retry_count": state.get("retry_count", 0)}

    if rag is None:
        rag_result = _empty_rag_result()
    else:
        rag_result = await rag.retrieve(Stage.REASON, state["user_query"], context={
            "matched_tables": state.get("matched_tables") or [],
        })
        # Also search Business KB for intent/query guidance (e.g., "产品→DISTINCT category")
        from rag.router import Stage as RStage
        biz_result = await rag.retrieve(RStage.UNDERSTAND, state["user_query"], context={})
        biz_rules = [m for m in biz_result.matches if "biz:" in m.get("id", "")]

    schema_detail = "\n".join(m.get("document", "") for m in rag_result.matches)
    extra_rules = "\n".join(m.get("document", "") for m in biz_rules) if biz_rules else ""
    business_rules = state.get("business_terms") or {}
    if extra_rules:
        business_rules["_query_guidance"] = extra_rules
    if reflect_guidance:
        business_rules["_reflect_fix"] = reflect_guidance

    prompt_text = prompts.render("reason.j2", {
        "user_query": state["user_query"],
        "matched_tables": state.get("matched_tables") or [],
        "schema_detail": schema_detail,
        "business_rules": business_rules,
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
