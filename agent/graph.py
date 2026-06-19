"""LangGraph state machine — assembles all 8 agent nodes with conditional routing."""
from typing import Literal
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.understand import understand_node
from agent.nodes.reason import reason_node
from agent.nodes.act import act_node
from agent.nodes.reflect import reflect_node
from agent.nodes.analyze import analyze_node
from agent.nodes.clarify import clarify_node
from agent.nodes.degrade import degrade_node
from agent.nodes.escalate import escalate_node
from evaluator.rules import SQLEvaluator
from evaluator.gates.sql_eval import sql_evaluator_gate
from evaluator.gates.result_eval import result_evaluator_gate
from evaluator.gates.output_eval import output_evaluator_gate
from evaluator.judge import LLMJudge
from monitoring.tracer import ThinkingTracer


def route_after_understand(state: AgentState) -> Literal["reason", "clarify"]:
    if state.get("clarification_question"):
        return "clarify"
    return "reason"


def route_after_sql_eval(state: AgentState) -> Literal["act", "reason", "escalate"]:
    results = state.get("evaluator_results", [])
    if results and results[-1].get("verdict") == "reject":
        # Count SQL eval rejections to prevent infinite REASON loop
        sql_retries = sum(1 for r in results if r.get("gate") == 1 and r.get("verdict") == "reject")
        if sql_retries >= 3:
            return "escalate"
        return "reason"
    return "act"


def route_after_act(state: AgentState) -> Literal["result_eval", "reflect", "escalate"]:
    if state.get("sql_error"):
        if state.get("retry_count", 0) >= 3:
            return "escalate"
        return "reflect"
    return "result_eval"


def route_after_result_eval(state: AgentState) -> Literal["analyze", "reason", "degrade"]:
    results = state.get("evaluator_results", [])
    if results:
        last = results[-1]
        retries = sum(1 for r in results if r.get("gate") == 2 and r.get("verdict") == "reflect")
        if last.get("verdict") == "reflect" and retries < 3:
            return "reason"
        if last.get("verdict") == "degrade":
            return "degrade"
    return "analyze"


def route_after_output_eval(state: AgentState) -> Literal["__end__", "analyze"]:
    results = state.get("evaluator_results", [])
    if results and results[-1].get("verdict") == "reject":
        output_retries = sum(1 for r in results if r.get("gate") == 3 and r.get("verdict") == "reject")
        if output_retries < 2:
            return "analyze"
    return "__end__"


def build_agent_graph(
    llm,
    dw,
    rag,
    prompts,
    tracer: ThinkingTracer,
    sql_evaluator: SQLEvaluator,
):
    """Build the complete LangGraph agent state machine."""
    graph = StateGraph(AgentState)

    llm_judge = LLMJudge(llm)

    # Add all 11 nodes (8 agent + 3 evaluator gates)
    async def _understand(s): return await understand_node(s, llm, rag, prompts, tracer)
    async def _reason(s): return await reason_node(s, llm, rag, prompts, tracer)
    async def _sql_eval(s): return await sql_evaluator_gate(s, sql_evaluator, llm_judge, tracer)
    async def _act(s): return await act_node(s, dw, tracer)
    async def _reflect(s): return await reflect_node(s, llm, rag, prompts, tracer)
    async def _result_eval(s): return await result_evaluator_gate(s, llm_judge, tracer)
    async def _analyze(s): return await analyze_node(s, llm, rag, prompts, tracer)
    async def _output_eval(s): return await output_evaluator_gate(s, llm_judge, tracer)
    async def _clarify(s): return await clarify_node(s, tracer)
    async def _degrade(s): return await degrade_node(s, tracer)
    async def _escalate(s): return await escalate_node(s, tracer)

    graph.add_node("understand", _understand)
    graph.add_node("reason", _reason)
    graph.add_node("sql_eval", _sql_eval)
    graph.add_node("act", _act)
    graph.add_node("reflect", _reflect)
    graph.add_node("result_eval", _result_eval)
    graph.add_node("analyze", _analyze)
    graph.add_node("output_eval", _output_eval)
    graph.add_node("clarify", _clarify)
    graph.add_node("degrade", _degrade)
    graph.add_node("escalate", _escalate)

    # Entry
    graph.set_entry_point("understand")

    # Conditional edges
    graph.add_conditional_edges("understand", route_after_understand, {"reason": "reason", "clarify": "clarify"})
    graph.add_edge("reason", "sql_eval")
    graph.add_conditional_edges("sql_eval", route_after_sql_eval, {"act": "act", "reason": "reason", "escalate": "escalate"})
    graph.add_conditional_edges("act", route_after_act, {"result_eval": "result_eval", "reflect": "reflect", "escalate": "escalate"})
    graph.add_edge("reflect", "reason")  # Always retry after reflect
    graph.add_conditional_edges("result_eval", route_after_result_eval, {"analyze": "analyze", "reason": "reason", "degrade": "degrade"})
    graph.add_edge("analyze", "output_eval")
    graph.add_conditional_edges("output_eval", route_after_output_eval, {"analyze": "analyze", "__end__": END})

    # Terminal nodes
    graph.add_edge("clarify", END)
    graph.add_edge("degrade", END)
    graph.add_edge("escalate", END)

    return graph.compile()
