"""Report API routes."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.dependencies import get_llm, get_dw, get_prompts
from report.planner import ReportPlanner
from report.assembler import ReportAssembler
from report.renderer import ReportRenderer
from monitoring.tracer import ThinkingTracer

router = APIRouter(prefix="/reports", tags=["reports"])

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "report" / "templates"


class ReportRequest(BaseModel):
    query: str
    template: str = "topic"  # weekly, monthly, topic


@router.post("/generate")
async def generate_report(req: ReportRequest):
    """Generate a structured report from natural language query + template."""
    llm = get_llm()
    dw = get_dw()
    prompts = get_prompts()
    tracer = ThinkingTracer()

    # Gather schema context so LLM knows actual table/column names + date ranges
    schema_lines = []
    try:
        tables = await dw.list_tables()
        for t in tables[:12]:
            schema = await dw.describe(t)
            cols = ", ".join(f"{c.name} ({c.dtype})" for c in schema.columns)
            schema_lines.append(f"  {t}: {cols}")
        # Add data date range to prevent LLM from using CURRENT_DATE filters
        date_range = await dw.execute(
            "SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM orders"
        )
        if date_range.rows:
            schema_lines.append(f"\n  DATA DATE RANGE: {date_range.rows[0][0]} to {date_range.rows[0][1]}")
            schema_lines.append(f"  DO NOT use CURRENT_DATE or INTERVAL — data is historical.")
    except Exception:
        schema_lines = ["(schema unavailable)"]
    schema_context = "\n".join(schema_lines)

    # 1. Plan: turn query + template into a report outline with SQL queries
    planner = ReportPlanner(prompts, llm, str(TEMPLATE_DIR))
    try:
        outline = await planner.plan_from_query(
            req.query, req.template,
            schema_context=schema_context,
        )
    except Exception as e:
        raise HTTPException(500, f"Report planning failed: {e}")

    # 2. Assemble: execute each section's SQL in parallel, generate AI insights
    assembler = ReportAssembler(dw, llm, prompts, tracer, max_parallel=3)
    sections = await assembler.assemble(outline)

    # 3. Render: format into final report payload
    title = outline.get("title", f"Report: {req.query[:50]}")
    renderer = ReportRenderer()
    report = renderer.render(title, sections)

    return {
        "report": report,
        "trace": tracer.to_dict(),
    }


@router.get("/")
async def list_reports():
    return {"reports": []}


@router.get("/{report_id}")
async def get_report(report_id: str):
    return {"report_id": report_id, "status": "not_implemented"}


@router.post("/export/markdown")
async def export_report_markdown(req: ReportRequest):
    """Generate and export a report as Markdown text (downloadable)."""
    from fastapi.responses import PlainTextResponse
    llm = get_llm()
    dw = get_dw()
    prompts = get_prompts()
    tracer = ThinkingTracer()

    tables = await dw.list_tables()
    schema_lines = []
    for t in tables[:12]:
        schema = await dw.describe(t)
        cols = ", ".join(f"{c.name} ({c.dtype})" for c in schema.columns)
        schema_lines.append(f"  {t}: {cols}")
    schema_context = "\n".join(schema_lines)

    planner = ReportPlanner(prompts, llm, str(TEMPLATE_DIR))
    outline = await planner.plan_from_query(req.query, req.template, schema_context=schema_context)
    assembler = ReportAssembler(dw, llm, prompts, tracer, max_parallel=3)
    sections = await assembler.assemble(outline)

    # Build Markdown
    md = f"# {outline.get('title', req.query)}\n\n"
    for s in sections:
        md += f"## {s.get('title', 'Section')}\n\n"
        md += f"{s.get('insight', 'No data available.')}\n\n"
        if s.get('chart_config'):
            md += f"_Chart: {s['chart_config'].get('chart_type', 'bar')}_\n\n"

    return PlainTextResponse(md, media_type="text/markdown",
                             headers={"Content-Disposition": f"attachment; filename=report.md"})
