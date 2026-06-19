"""REFLECT node — diagnose SQL errors and propose corrections."""
import json
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


def _empty_rag_result() -> RAGResult:
    return RAGResult(matches=[], strategy_name="noop", confidence=1.0)


async def reflect_node(
    state: AgentState, llm: BaseLLMProvider, rag: RAGRouter,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("REFLECT")
    error_msg = state.get("sql_error") or ""
    failed_sql = state.get("generated_sql") or ""
    retry_count = (state.get("retry_count") or 0) + 1

    if rag is None:
        rag_result = _empty_rag_result()
    else:
        rag_result = await rag.retrieve(Stage.REFLECT, error_msg, context={
            "failed_sql": failed_sql, "error_message": error_msg,
            "matched_tables": state.get("matched_tables") or [],
        })

    corrections = {}
    for m in rag_result.matches:
        if "corrections" in m:
            corrections.update(m["corrections"])

    fix_text = "\n".join(f"  - '{k}' should be '{v}'" for k, v in corrections.items()) if corrections else "No suggestions."

    prompt_text = prompts.render("reflect.j2", {
        "failed_sql": failed_sql, "error_message": error_msg,
        "schema_context": "", "fix_suggestions": fix_text,
    })

    response = await llm.chat([
        Message(role="system", content="Fix the SQL. Return JSON with 'sql' field."),
        Message(role="user", content=prompt_text),
    ])
    usage = response.usage or {}
    tracer.add_tokens(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    try:
        data = json.loads(response.content)
        new_sql = data.get("sql", failed_sql)
    except json.JSONDecodeError:
        new_sql = failed_sql

    tracer.record_step_end("REFLECT", {"retry_count": retry_count, "new_sql": new_sql[:500]})
    return {"generated_sql": new_sql, "retry_count": retry_count, "sql_error": None}
