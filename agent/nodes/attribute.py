"""ATTRIBUTE node — drill-down analysis for 'why' questions."""
import json
from agent.state import AgentState
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message
from connectors.dw.base import BaseDWConnector
from monitoring.tracer import ThinkingTracer
from monitoring.logger import get_logger

_log = get_logger("agent.attribute")


async def attribute_node(
    state: AgentState, llm: BaseLLMProvider, dw: BaseDWConnector,
    prompts: PromptManager, tracer: ThinkingTracer,
) -> dict:
    tracer.record_step_start("ATTRIBUTE")
    user_query = state.get("user_query") or ""
    current_sql = state.get("generated_sql") or ""
    matched_tables = state.get("matched_tables") or []
    current_answer = state.get("analysis_text") or ""
    query_result = state.get("query_result") or {}

    # 1. LLM identifies key dimensions for drill-down
    drill_prompt = prompts.render("attribute.j2", {
        "user_query": user_query,
        "current_sql": current_sql[:500],
        "current_answer": current_answer[:500],
        "matched_tables": matched_tables,
        "columns": query_result.get("columns", []),
        "sample_rows": str(query_result.get("rows", [])[:3]),
    })

    response = await llm.chat([
        Message(role="system", content="You are a data analyst. Return JSON with drill-down queries in Chinese."),
        Message(role="user", content=drill_prompt),
    ])

    try:
        drill_plan = json.loads(response.content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown
        import re
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        drill_plan = json.loads(match.group(0)) if match else {"dimensions": []}

    dimensions = drill_plan.get("dimensions", [])

    # 2. Execute each drill-down query
    findings = []
    for dim in dimensions[:4]:  # Max 4 dimensions to keep latency reasonable
        dim_name = dim.get("dimension", dim.get("name", "unknown"))
        dim_sql = dim.get("sql", "")
        if not dim_sql:
            continue

        try:
            result = await dw.execute(dim_sql)
            rows = [list(r) for r in result.rows]
            cols = result.columns

            # 3. Quick analysis of this dimension
            if rows:
                # Find the biggest contributor
                top_contributor = ""
                if len(cols) >= 2 and len(rows) >= 1:
                    top_contributor = f"{cols[0]}={rows[0][0]}, {cols[1]}={rows[0][1]}"
                    if len(rows) >= 2:
                        top_contributor += f" (2nd: {cols[0]}={rows[1][0]}, {cols[1]}={rows[1][1]})"

                findings.append({
                    "dimension": dim_name,
                    "rows": len(rows),
                    "top": top_contributor,
                    "data": {"columns": cols, "rows": rows[:5]},
                })
        except Exception as e:
            findings.append({
                "dimension": dim_name,
                "error": str(e)[:100],
            })

    # 4. LLM summarizes attribution findings into readable insights
    if findings:
        findings_text = json.dumps(findings, ensure_ascii=False, default=str)
        summary_response = await llm.chat([
            Message(role="system", content="Summarize drill-down findings in 3-5 Chinese sentences. Identify the main contributing factor."),
            Message(role="user", content=f"Original question: {user_query}\nDrill-down results: {findings_text[:2000]}\nWrite a concise attribution summary in Chinese."),
        ])
        attribution_text = f"\n\n---\n**归因分析：**\n{summary_response.content.strip()}"
    else:
        attribution_text = "\n\n(归因分析未找到显著维度差异)"

    full_answer = current_answer + attribution_text

    _log.info(f"Attribution complete: {len(findings)} dimensions analyzed")
    tracer.record_step_end("ATTRIBUTE", {
        "dimensions": len(findings),
        "findings": [f.get("dimension", "") for f in findings],
    })

    return {
        "analysis_text": full_answer,
        "query_result": query_result,
    }
