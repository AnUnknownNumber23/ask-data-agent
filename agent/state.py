"""Agent state schema for LangGraph state machine."""
from typing import TypedDict, Annotated, Sequence, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """State that flows through the LangGraph agent nodes."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    user_query: str
    intent: dict[str, Any]
    matched_tables: list[str]
    business_terms: dict[str, str]
    generated_sql: str
    sql_error: str | None
    retry_count: int
    query_result: dict[str, Any] | None
    result_summary: str
    analysis_text: str
    chart_config: dict[str, Any] | None
    evaluator_results: list[dict[str, Any]]
    clarification_question: str | None
    degradation_message: str | None
    escalation_ticket: dict[str, Any] | None
    is_report_mode: bool
    report_outline: dict[str, Any] | None
    report_sections: list[dict[str, Any]]
    # Multi-round ReAct
    react_round: int
    accumulated_rounds: list[dict[str, Any]]
    react_max_rounds: int
    _check_complete: bool
    _check_next_step: str
    _check_needs_attribution: bool
    _check_needs_forecast: bool
