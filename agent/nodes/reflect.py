"""REFLECT node — diagnose SQL errors and propose corrections."""
import json
from agent.state import AgentState
from monitoring.logger import get_logger

_log = get_logger("agent.reflect")
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

    # --- Direct fix: apply known function name replacements ---
    import re as _re
    # Simple name replacements (compatible args)
    for wrong, right in [("DATE_FORMAT", "STRFTIME"), ("TO_CHAR", "STRFTIME")]:
        failed_sql = _re.sub(wrong, right, failed_sql, flags=_re.IGNORECASE)
    # TO_DAYS arithmetic -> DATEDIFF (handle both bare col and table.col)
    to_days_match = _re.search(
        r'TO_DAYS\(([\w.]+)\)\s*-\s*TO_DAYS\(([\w.]+)\)',
        failed_sql, _re.IGNORECASE
    )
    if to_days_match:
        end_col, start_col = to_days_match.group(1), to_days_match.group(2)
        failed_sql = _re.sub(
            r'TO_DAYS\([\w.]+\)\s*-\s*TO_DAYS\([\w.]+\)',
            f"DATEDIFF('day', {start_col}, {end_col})",
            failed_sql, flags=_re.IGNORECASE
        )
    direct_fix_applied = (failed_sql != state.get("generated_sql", ""))

    if direct_fix_applied:
        new_sql = failed_sql
        _log.warning(f"Direct fix applied: retry#{retry_count}, error={error_msg[:100]}")
    elif prompts is not None and llm is not None:
        # Fall back to LLM-based fix
        fix_text = "\n".join(f"  - '{k}' should be '{v}'" for k, v in corrections.items()) if corrections else "Check column names against schema."

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
    else:
        new_sql = failed_sql

    result_state = {"generated_sql": new_sql, "retry_count": retry_count, "sql_error": None}
    if direct_fix_applied:
        # Tell REASON to use the corrected SQL, don't regenerate from scratch
        result_state["_reflect_guidance"] = (
            f"CRITICAL: Previous SQL failed with: {error_msg[:100]}. "
            f"Corrected SQL: {new_sql}. Use this version — do NOT use the original broken functions."
        )
    tracer.record_step_end("REFLECT", {"retry_count": retry_count, "new_sql": new_sql[:500]})
    return result_state
