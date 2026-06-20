"""UNDERSTAND node — parse user intent via RAG + LLM."""
import json
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.understand")


def _empty_rag_result() -> RAGResult:
    return RAGResult(matches=[], strategy_name="noop", confidence=1.0)


async def understand_node(
    state: AgentState,
    llm: BaseLLMProvider,
    rag: RAGRouter,
    prompts: PromptManager,
    tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("UNDERSTAND")
    query = state["user_query"]

    if rag is None:
        rag_result = _empty_rag_result()
    else:
        rag_result = await rag.retrieve(Stage.UNDERSTAND, query, context={})

    # Skip clarification for prediction/forecast queries — they always need historical data
    skip_clarify_keywords = ["预测", "预计", "趋势", "forecast", "predict", "trend", "projection", "将来", "未来", "下一"]
    is_prediction = any(kw in query.lower() for kw in skip_clarify_keywords)

    if is_prediction and not rag_result.matches:
        # Fallback: prediction always needs orders + order_items for time series
        rag_result = RAGResult(
            matches=[{"id": "table:orders", "document": "Table orders with order_purchase_timestamp"},
                      {"id": "table:order_items", "document": "Table order_items with price"}],
            strategy_name="prediction_fallback",
            confidence=0.7,
        )

    if rag_result.confidence < 0.65 and not rag_result.matches and not is_prediction:
        _log.warning(f"No tables matched, routing to CLARIFY: {query[:80]}")
        tracer.record_step_end("UNDERSTAND", {"matched_tables": [], "action": "CLARIFY"}, status="warning")
        return {
            "intent": {},
            "matched_tables": [],
            "clarification_question": "I couldn't find matching data tables for your question. Could you specify what kind of data you're looking for?",
        }

    # Separate schema from business context
    schema_matches = [m for m in rag_result.matches if "biz:" not in m.get("id", "")]
    biz_matches = [m for m in rag_result.matches if "biz:" in m.get("id", "")]
    schema_context = "\n".join(m.get("document", "") for m in schema_matches)
    business_context = "\n".join(m.get("document", "") for m in biz_matches)
    # Build conversation history string from state messages
    conversation_history = ""
    history_msgs = state.get("messages") or []
    if history_msgs:
        lines = []
        for msg in history_msgs[-6:]:  # Last 3 Q&A pairs
            # Handle both dict and LangGraph message types
            try:
                role = msg.get("role", "") if hasattr(msg, "get") else getattr(msg, "type", "user")
                content = msg.get("content", "") if hasattr(msg, "get") else getattr(msg, "content", "")
                if role in ("human", "user"): role = "User"
                else: role = "Assistant"
                lines.append(f"{role}: {str(content)[:200]}")
            except Exception:
                pass
        conversation_history = "\n".join(lines) if lines else ""

    prompt_text = prompts.render("understand.j2", {
        "user_query": query,
        "schema_context": schema_context,
        "business_context": business_context,
        "conversation_history": conversation_history,
    })

    response = await llm.chat([
        Message(role="system", content="You are a data analyst. Return valid JSON only."),
        Message(role="user", content=prompt_text),
    ])
    usage = response.usage or {}
    tracer.add_tokens(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    try:
        intent = json.loads(response.content)
    except json.JSONDecodeError:
        intent = {"matched_tables": [], "confidence": 0.0, "needs_clarification": True,
                  "clarification_question": "I had trouble understanding. Could you rephrase?"}

    tables = intent.get("matched_tables", [])
    confidence = intent.get("confidence", 0.0)
    _log.info(f"Intent parsed: tables={tables}, confidence={confidence:.2f}")

    tracer.record_step_end("UNDERSTAND", {
        "matched_tables": tables,
        "confidence": confidence,
    })

    if intent.get("needs_clarification"):
        return {"intent": intent, "matched_tables": [], "clarification_question": intent.get("clarification_question")}

    return {"intent": intent, "matched_tables": intent.get("matched_tables", []),
            "business_terms": intent.get("business_terms", {})}
