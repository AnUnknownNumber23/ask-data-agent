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

    # 1. Plan: turn query + template into a report outline with SQL queries
    planner = ReportPlanner(prompts, llm, str(TEMPLATE_DIR))
    try:
        outline = await planner.plan_from_query(req.query, req.template)
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
