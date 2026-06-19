"""Chat API routes — POST /chat and WS /ws/chat."""
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from api.dependencies import get_llm, get_dw, get_prompts, get_sql_evaluator, get_config, get_rag
from api.ws import ws_manager
from agent.graph import build_agent_graph
from agent.state import AgentState
from memory.session import get_session_store
from monitoring.tracer import ThinkingTracer
router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:8]
    llm = get_llm()
    dw = get_dw()
    prompts = get_prompts()
    tracer = ThinkingTracer()
    sql_eval = get_sql_evaluator()
    config = get_config()
    rag = await get_rag()
    graph = build_agent_graph(llm, dw, rag, prompts, tracer, sql_eval)

    tracer.start(session_id, req.query)
    initial_state: AgentState = {
        "messages": [], "session_id": session_id, "user_query": req.query,
        "intent": {}, "matched_tables": [], "business_terms": {},
        "generated_sql": "", "sql_error": None, "retry_count": 0,
        "query_result": None, "result_summary": "",
        "analysis_text": "", "chart_config": None, "evaluator_results": [],
        "clarification_question": None, "degradation_message": None, "escalation_ticket": None,
        "is_report_mode": False, "report_outline": None, "report_sections": [],
    }

    result = await graph.ainvoke(initial_state)

    answer = (result.get("analysis_text", "")
              or result.get("clarification_question", "")
              or result.get("degradation_message", "")
              or result.get("escalation_ticket", "")
              or "Analysis complete.")
    total_chars = len(str(answer)) + len(result.get("generated_sql", ""))
    tracer.finalize({"input": max(1, total_chars // 2), "output": max(1, total_chars // 3)})
    trace_data = tracer.to_dict()

    return {
        "session_id": session_id,
        "answer": answer,
        "chart": result.get("chart_config"),
        "trace": trace_data,
    }


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    session_id = str(uuid.uuid4())[:8]
    await ws_manager.connect(session_id, websocket)
    session_store = get_session_store()

    async def ws_sender(data: dict):
        await ws_manager.send(session_id, data)

    try:
        tracer = ThinkingTracer(websocket_sender=ws_sender)
        llm = get_llm()
        dw = get_dw()
        prompts = get_prompts()
        sql_eval = get_sql_evaluator()
        config = get_config()
        rag = await get_rag()
    except Exception as e:
        await ws_manager.send(session_id, {
            "type": "error",
            "message": f"Agent init failed: {str(e)}",
        })
        ws_manager.disconnect(session_id)
        return

    # Send session ID to frontend for persistence
    await ws_manager.send(session_id, {
        "type": "session",
        "session_id": session_id,
        "history": session_store.get_history(session_id),
    })

    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")

            # Accept client session ID for cross-connection continuity
            client_sid = data.get("session_id", "")
            storage_sid = session_id  # the ID used for session store and history
            if client_sid and client_sid != session_id:
                storage_sid = client_sid  # Use client's session for storage only
                # IMPORTANT: do NOT change session_id — it's captured by ws_sender closure
                # and must match the WebSocket connection registration
            history = session_store.format_for_prompt(storage_sid)

            tracer.start(session_id, query)

            graph = build_agent_graph(llm, dw, rag, prompts, tracer, sql_eval)

            # Inject conversation history into state for understand node
            history_messages = []
            for turn in session_store.get_history(session_id)[-5:]:
                history_messages.append({"role": "user", "content": turn["query"]})
                history_messages.append({"role": "assistant", "content": turn["answer"][:200]})

            initial_state: AgentState = {
                "messages": history_messages, "session_id": session_id, "user_query": query,
                "intent": {}, "matched_tables": [], "business_terms": {},
                "generated_sql": "", "sql_error": None, "retry_count": 0,
                "query_result": None, "result_summary": "",
                "analysis_text": "", "chart_config": None, "evaluator_results": [],
                "clarification_question": None, "degradation_message": None, "escalation_ticket": None,
                "is_report_mode": False, "report_outline": None, "report_sections": [],
            }

            try:
                result = await graph.ainvoke(initial_state)

                answer = (result.get("analysis_text", "")
                          or result.get("clarification_question", "")
                          or result.get("degradation_message", "")
                          or result.get("escalation_ticket", "")
                          or "Analysis complete.")

                # Save this turn to session history
                session_store.add_turn(
                    storage_sid, query, str(answer),
                    result.get("matched_tables", []),
                    result.get("generated_sql", ""),
                )

                # Estimate tokens from response + SQL length
                total_chars = len(str(answer)) + len(result.get("generated_sql", ""))
                tracer.finalize({"input": max(1, total_chars // 2), "output": max(1, total_chars // 3)})

                await ws_manager.send(session_id, {
                    "type": "done",
                    "answer": str(answer),
                    "chart": result.get("chart_config"),
                    "trace": tracer.to_dict(),
                })
            except Exception as e:
                await ws_manager.send(session_id, {
                    "type": "error",
                    "message": f"Analysis failed: {str(e)}",
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
    except Exception:
        ws_manager.disconnect(session_id)
