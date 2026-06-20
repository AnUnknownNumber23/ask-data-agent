"""CHECK node — verifies if the user's question has been fully answered.

If not, determines what additional data/analysis is needed and routes back
to REASON for another round. This replaces the old ATTRIBUTE/PREDICT nodes.
"""
import json
from agent.state import AgentState
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.check")


async def check_node(
    state: AgentState, llm: BaseLLMProvider,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("CHECK")
    user_query = state.get("user_query") or ""
    current_round = (state.get("react_round") or 0) + 1
    max_rounds = state.get("react_max_rounds") or 5
    current_sql = state.get("generated_sql") or ""
    current_answer = state.get("analysis_text") or ""
    query_result = state.get("query_result") or {}
    rounds = list(state.get("accumulated_rounds") or [])

    # Record this round
    rounds.append({
        "round": current_round - 1,
        "sql": current_sql[:300],
        "rows": query_result.get("total_returned", 0) if query_result else 0,
        "insight": current_answer[:300],
    })

    # Build prompt
    rounds_text = json.dumps(rounds, ensure_ascii=False, default=str) if rounds else "first round"
    prompt_text = prompts.render("check.j2", {
        "user_query": user_query,
        "current_round": current_round,
        "max_rounds": max_rounds,
        "rounds_history": rounds_text,
        "current_sql": current_sql[:500],
        "current_answer": current_answer[:500],
    })

    response = await llm.chat([
        Message(role="system", content="You verify if analysis is complete. Return JSON."),
        Message(role="user", content=prompt_text),
    ])

    try:
        decision = json.loads(response.content)
    except json.JSONDecodeError:
        decision = {"complete": True, "reason": "Analysis complete"}

    complete = decision.get("complete", True)
    reason = decision.get("reason") or ""
    next_step = decision.get("next_step") or ""
    needs_attribution = decision.get("needs_attribution", False)
    needs_forecast = decision.get("needs_forecast", False)

    _log.info(f"CHECK round={current_round}/{max_rounds} complete={complete} attr={needs_attribution} fcst={needs_forecast}")

    tracer.record_step_end("CHECK", {
        "complete": complete,
        "reason": (reason or "")[:200],
        "next_step": (next_step or "")[:200],
        "needs_attribution": needs_attribution,
        "needs_forecast": needs_forecast,
    })

    return {
        "react_round": current_round,
        "accumulated_rounds": rounds,
        "analysis_text": current_answer,
        "_check_complete": complete,
        "_check_next_step": next_step,
        "_check_needs_attribution": needs_attribution,
        "_check_needs_forecast": needs_forecast,
    }
