"""Chat API routes — POST /chat and WS /ws/chat."""
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from api.dependencies import get_llm, get_dw, get_prompts, get_sql_evaluator, get_config
from api.ws import ws_manager
from agent.graph import build_agent_graph
from agent.state import AgentState
from monitoring.tracer import ThinkingTracer
from rag.router import RAGRouter

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
    rag = RAGRouter(kbs={}, config=config["rag"]["retrieval"])
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
    trace_data = tracer.to_dict()

    return {
        "session_id": session_id,
        "answer": result.get("analysis_text", result.get("clarification_question", "Analysis complete.")),
        "chart": result.get("chart_config"),
        "trace": trace_data,
    }


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    session_id = str(uuid.uuid4())[:8]
    await ws_manager.connect(session_id, websocket)

    async def ws_sender(data: dict):
        await ws_manager.send(session_id, data)

    tracer = ThinkingTracer(websocket_sender=ws_sender)
    llm = get_llm()
    dw = get_dw()
    prompts = get_prompts()
    sql_eval = get_sql_evaluator()
    config = get_config()

    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            tracer.start(session_id, query)

            rag = RAGRouter(kbs={}, config=config["rag"]["retrieval"])
            graph = build_agent_graph(llm, dw, rag, prompts, tracer, sql_eval)

            initial_state: AgentState = {
                "messages": [], "session_id": session_id, "user_query": query,
                "intent": {}, "matched_tables": [], "business_terms": {},
                "generated_sql": "", "sql_error": None, "retry_count": 0,
                "query_result": None, "result_summary": "",
                "analysis_text": "", "chart_config": None, "evaluator_results": [],
                "clarification_question": None, "degradation_message": None, "escalation_ticket": None,
                "is_report_mode": False, "report_outline": None, "report_sections": [],
            }

            result = await graph.ainvoke(initial_state)

            await ws_manager.send(session_id, {
                "type": "done",
                "answer": result.get("analysis_text", ""),
                "chart": result.get("chart_config"),
                "trace": tracer.to_dict(),
            })

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
