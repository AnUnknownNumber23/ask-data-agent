"""UNDERSTAND node — parse user intent via RAG + LLM."""
import json
from agent.state import AgentState
from rag.router import RAGRouter, Stage
from rag.strategies.base import RAGResult
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer


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

    if rag_result.confidence < 0.65 and not rag_result.matches:
        tracer.record_step_end("UNDERSTAND", {"matched_tables": [], "action": "CLARIFY"}, status="warning")
        return {
            "intent": {},
            "matched_tables": [],
            "clarification_question": "I couldn't find matching data tables for your question. Could you specify what kind of data you're looking for?",
        }

    schema_context = "\n".join(m.get("document", "") for m in rag_result.matches)
    # Build conversation history string from state messages
    conversation_history = ""
    history_msgs = state.get("messages", [])
    if history_msgs:
        lines = []
        for msg in history_msgs[-6:]:  # Last 3 Q&A pairs
            role = "User" if msg.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {msg.get('content', '')[:200]}")
        conversation_history = "\n".join(lines)

    prompt_text = prompts.render("understand.j2", {
        "user_query": query,
        "schema_context": schema_context,
        "business_context": "",
        "conversation_history": conversation_history,
    })

    response = await llm.chat([
        Message(role="system", content="You are a data analyst. Return valid JSON only."),
        Message(role="user", content=prompt_text),
    ])

    try:
        intent = json.loads(response.content)
    except json.JSONDecodeError:
        intent = {"matched_tables": [], "confidence": 0.0, "needs_clarification": True,
                  "clarification_question": "I had trouble understanding. Could you rephrase?"}

    tracer.record_step_end("UNDERSTAND", {
        "matched_tables": intent.get("matched_tables", []),
        "confidence": intent.get("confidence", 0.0),
    })

    if intent.get("needs_clarification"):
        return {"intent": intent, "matched_tables": [], "clarification_question": intent.get("clarification_question")}

    return {"intent": intent, "matched_tables": intent.get("matched_tables", []),
            "business_terms": intent.get("business_terms", {})}
