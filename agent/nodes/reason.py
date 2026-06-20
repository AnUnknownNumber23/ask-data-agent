"""REASON node — generate SQL from intent + table schema."""
import json
import re
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.reason")


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
            _log.info(f"SQL pass-through from REFLECT fix ({len(corrected_sql)} chars)")
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
    # Inject date range constraint if available
    if rag is not None:
        skb = rag.kbs.get("schema_kb")
        if skb:
            try:
                date_doc = skb.collection.get(ids=["meta:date_range"])
                if date_doc and date_doc.get("documents"):
                    schema_detail += "\n" + date_doc["documents"][0]
            except Exception:
                pass
    extra_rules = "\n".join(m.get("document", "") for m in biz_rules) if biz_rules else ""
    business_rules = state.get("business_terms") or {}
    if extra_rules:
        business_rules["_query_guidance"] = extra_rules
    if reflect_guidance:
        business_rules["_reflect_fix"] = reflect_guidance

    # Multi-round context: pass previous rounds so LLM knows what's already been done
    accumulated = state.get("accumulated_rounds") or []
    prev_rounds_text = ""
    if accumulated:
        prev_rounds_text = "Previous rounds of analysis:\n"
        for r in accumulated:
            prev_rounds_text += f"- Round {r['round']}: SQL={r.get('sql','')[:150]}, Rows={r.get('rows',0)}, Insight={r.get('insight','')[:150]}\n"

    check_hint = state.get("_check_next_step") or ""

    prompt_text = prompts.render("reason.j2", {
        "user_query": state["user_query"],
        "matched_tables": state.get("matched_tables") or [],
        "schema_detail": schema_detail,
        "business_rules": business_rules,
        "previous_rounds": prev_rounds_text,
        "check_hint": check_hint,
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

    _log.info(f"SQL generated ({len(sql)} chars): {sql[:150]}")
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
