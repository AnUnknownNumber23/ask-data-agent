"""ACT node — execute SQL against DW."""
from agent.state import AgentState
from connectors.dw.base import BaseDWConnector
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.act")


async def act_node(state: AgentState, dw: BaseDWConnector, tracer: ThinkingTracer) -> dict:
    tracer.record_step_start("ACT")
    sql = state.get("generated_sql") or ""

    if not sql:
        tracer.record_step_end("ACT", {}, status="error", error="No SQL generated")
        return {"sql_error": "No SQL was generated"}

    try:
        _log.debug(f"Executing: {sql[:200]}")
        result = await dw.execute(sql)
        _log.info(f"SQL executed: {result.total_returned} rows in {result.execution_ms:.0f}ms")
        tracer.record_step_end("ACT", {
            "columns": result.columns,
            "row_count": result.total_returned,
            "execution_ms": result.execution_ms,
        })
        return {
            "query_result": {
                "columns": result.columns,
                "rows": [list(r) for r in result.rows],
                "total_returned": result.total_returned,
                "execution_ms": result.execution_ms,
            },
            "sql_error": None,
        }
    except Exception as e:
        error_msg = str(e)
        _log.error(f"SQL execution failed: {error_msg[:200]}")
        tracer.record_step_end("ACT", {}, status="error", error=error_msg)
        return {"sql_error": error_msg}
