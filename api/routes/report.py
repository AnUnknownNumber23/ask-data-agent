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

    # 3. Post-processing: attribution / prediction if query calls for it
    query_lower = req.query.lower()
    if any(kw in query_lower for kw in ["why", "为什么", "原因", "跌了", "下降"]):
        # Run attribution: drill down on key metric sections
        from agent.nodes.attribute import attribute_node
        attr_state = {
            "user_query": req.query, "generated_sql": "",
            "analysis_text": "\n".join(s.get("insight", "") for s in sections if s.get("insight")),
            "matched_tables": [], "query_result": None,
        }
        attr_result = await attribute_node(attr_state, llm, dw, prompts, tracer)
        attr_text = attr_result.get("analysis_text", "")
        if attr_text:
            sections.append({
                "id": "attribution", "title": "归因分析",
                "type": "text", "insight": attr_text.replace(attr_state["analysis_text"], "").strip(),
            })

    if any(kw in query_lower for kw in ["predict", "forecast", "预测", "预计", "趋势"]):
        from agent.nodes.predict import predict_node
        pred_state = {
            "user_query": req.query, "generated_sql": "",
            "analysis_text": "\n".join(s.get("insight", "") for s in sections if s.get("insight")),
            "matched_tables": [], "query_result": None,
        }
        pred_result = await predict_node(pred_state, llm, dw, prompts, tracer)
        pred_text = pred_result.get("analysis_text", "")
        if pred_text:
            sections.append({
                "id": "prediction", "title": "趋势预测",
                "type": "text", "insight": pred_text.replace(pred_state["analysis_text"], "").strip(),
            })

    # 4. Render: format into final report payload
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


@router.post("/export/pdf")
async def export_report_pdf(req: ReportRequest):
    """Generate and export a report as PDF."""
    from fastapi.responses import Response
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    # Register Chinese font (try multiple options available on Windows)
    _cn_font_registered = False
    for font_name, font_path in [
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
        ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
    ]:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            CN_FONT = font_name
            _cn_font_registered = True
            break
        except Exception:
            continue
    if not _cn_font_registered:
        # Fallback: use built-in CID font (supports CJK but limited)
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        CN_FONT = 'STSong-Light'

    # Generate report first
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
    title = outline.get("title", req.query)

    # Build PDF
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=18, spaceAfter=20, alignment=TA_LEFT, fontName=CN_FONT)
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.5*cm))

    # Sections
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceBefore=16, spaceAfter=8, fontName=CN_FONT)
    body_style = ParagraphStyle('Body2', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=12, fontName=CN_FONT)

    for s in sections:
        sec_title = s.get("title", "Section")
        insight = s.get("insight", "No data available.")
        story.append(Paragraph(sec_title, h2_style))
        for para in insight.split('\n'):
            if para.strip():
                story.append(Paragraph(para.strip(), body_style))
        story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    buf.seek(0)

    filename = f"{title[:30]}.pdf".replace(" ", "_").replace("/", "_")
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})
