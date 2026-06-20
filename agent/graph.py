"""LangGraph state machine — ReAct loop with self-correction and auto-retry."""
from typing import Literal
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.understand import understand_node
from agent.nodes.reason import reason_node
from agent.nodes.act import act_node
from agent.nodes.reflect import reflect_node
from agent.nodes.analyze import analyze_node
from agent.nodes.check import check_node
from agent.nodes.clarify import clarify_node
from agent.nodes.escalate import escalate_node
from evaluator.rules import SQLEvaluator
from evaluator.gates.sql_eval import sql_evaluator_gate
from evaluator.gates.result_eval import result_evaluator_gate
from evaluator.gates.output_eval import output_evaluator_gate
from evaluator.judge import LLMJudge
from monitoring.tracer import ThinkingTracer


def route_after_understand(state: AgentState) -> Literal["reason", "clarify", "__end__"]:
    if state.get("clarification_question"):
        return "clarify"
    if state.get("analysis_text") and not state.get("matched_tables"):
        return "__end__"
    return "reason"


def route_after_sql_eval(state: AgentState) -> Literal["act", "reason", "escalate"]:
    results = state.get("evaluator_results") or []
    if results and results[-1].get("verdict") == "reject":
        sql_retries = sum(1 for r in results if r.get("gate") == 1 and r.get("verdict") == "reject")
        if sql_retries >= 3:
            return "escalate"
        return "reason"
    return "act"


def route_after_act(state: AgentState) -> Literal["result_eval", "reflect", "escalate"]:
    if state.get("sql_error"):
        if (state.get("retry_count") or 0) >= 3:
            return "escalate"
        return "reflect"
    return "result_eval"


def route_after_result_eval(state: AgentState) -> Literal["analyze", "reason"]:
    results = state.get("evaluator_results") or []
    if results:
        last = results[-1]
        if last.get("verdict") == "reflect":
            retries = sum(1 for r in results if r.get("gate") == 2 and r.get("verdict") == "reflect")
            if retries < 3:
                return "reason"
    return "analyze"


def route_after_check(state: AgentState) -> Literal["reason", "__end__", "escalate"]:
    """CHECK decides: continue ReAct loop or finish."""
    # If CHECK says complete -> end
    if state.get("_check_complete", True):
        return "__end__"
    # If max rounds reached -> end anyway
    if (state.get("react_round") or 0) >= (state.get("react_max_rounds") or 5):
        return "__end__"
    # Not complete, within limits -> another round
    return "reason"


def build_agent_graph(
    llm,
    dw,
    rag,
    prompts,
    tracer: ThinkingTracer,
    sql_evaluator: SQLEvaluator,
):
    """Build the ReAct agent graph with multi-round self-correction loop."""
    graph = StateGraph(AgentState)

    llm_judge = LLMJudge(llm)

    async def _understand(s): return await understand_node(s, llm, rag, prompts, tracer)
    async def _reason(s): return await reason_node(s, llm, rag, prompts, tracer)
    async def _sql_eval(s): return await sql_evaluator_gate(s, sql_evaluator, llm_judge, tracer)
    async def _act(s): return await act_node(s, dw, tracer)
    async def _reflect(s): return await reflect_node(s, llm, rag, prompts, tracer)
    async def _result_eval(s): return await result_evaluator_gate(s, llm_judge, tracer)
    async def _analyze(s): return await analyze_node(s, llm, rag, prompts, tracer)
    async def _check(s): return await check_node(s, llm, prompts, tracer)
    async def _output_eval(s): return await output_evaluator_gate(s, llm_judge, tracer)
    async def _clarify(s): return await clarify_node(s, tracer)
    async def _escalate(s): return await escalate_node(s, tracer)

    graph.add_node("understand", _understand)
    graph.add_node("reason", _reason)
    graph.add_node("sql_eval", _sql_eval)
    graph.add_node("act", _act)
    graph.add_node("reflect", _reflect)
    graph.add_node("result_eval", _result_eval)
    graph.add_node("analyze", _analyze)
    graph.add_node("check", _check)
    graph.add_node("output_eval", _output_eval)
    graph.add_node("clarify", _clarify)
    graph.add_node("escalate", _escalate)

    # Entry
    graph.set_entry_point("understand")

    # Inner ReAct loop: REASON → SQL_EVAL → ACT → RESULT_EVAL → ANALYZE
    graph.add_conditional_edges("understand", route_after_understand, {"reason": "reason", "clarify": "clarify", "__end__": END})
    graph.add_edge("reason", "sql_eval")
    graph.add_conditional_edges("sql_eval", route_after_sql_eval, {"act": "act", "reason": "reason", "escalate": "escalate"})
    graph.add_conditional_edges("act", route_after_act, {"result_eval": "result_eval", "reflect": "reflect", "escalate": "escalate"})
    graph.add_edge("reflect", "sql_eval")
    graph.add_conditional_edges("result_eval", route_after_result_eval, {"analyze": "analyze", "reason": "reason"})

    # After ANALYZE → CHECK
    graph.add_edge("analyze", "check")

    # CHECK routes back to REASON (another round) or to OUTPUT_EVAL (done)
    graph.add_conditional_edges("check", route_after_check, {"reason": "reason", "__end__": "output_eval", "escalate": "escalate"})
    graph.add_edge("output_eval", END)

    # Terminal
    graph.add_edge("clarify", END)
    graph.add_edge("escalate", END)

    return graph.compile()
