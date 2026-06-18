"""Report assembler — executes queries in parallel and generates AI insights per section."""
import asyncio
from connectors.dw.base import BaseDWConnector
from connectors.llm.base import BaseLLMProvider, Message
from prompts.manager import PromptManager
from monitoring.tracer import ThinkingTracer


class ReportAssembler:
    def __init__(self, dw: BaseDWConnector, llm: BaseLLMProvider, prompts: PromptManager,
                 tracer: ThinkingTracer, max_parallel: int = 3):
        self.dw = dw
        self.llm = llm
        self.prompts = prompts
        self.tracer = tracer
        self.max_parallel = max_parallel

    async def assemble(self, outline: dict) -> list[dict]:
        sections = outline.get("outline", [])
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def fetch_section(section: dict) -> dict:
            async with semaphore:
                query = section.get("query", "")
                if query:
                    try:
                        result = await self.dw.execute(query)
                        section["_data"] = {"columns": result.columns, "rows": [list(r) for r in result.rows], "total_returned": result.total_returned}
                    except Exception as e:
                        section["_data"] = {"error": str(e)}
                else:
                    section["_data"] = None
                return section

        sections_with_data = await asyncio.gather(*[fetch_section(s) for s in sections])

        assembled = []
        for section in sections_with_data:
            data = section.pop("_data", None)
            if data and "error" not in data:
                prompt = self.prompts.render("report_assemble.j2", {
                    "section_title": section.get("title", ""),
                    "section_type": section.get("type", ""),
                    "query_result": str(data)[:2000],
                    "chart_suggestions": self._suggest(section),
                })
                try:
                    response = await self.llm.chat([
                        Message(role="system", content="Return JSON with 'insight' and 'chart_config'."),
                        Message(role="user", content=prompt),
                    ])
                    import json
                    ai = json.loads(response.content)
                except Exception:
                    ai = {"insight": "Data retrieved.", "chart_config": None}
                section["insight"] = ai.get("insight", "")
                section["chart_config"] = ai.get("chart_config")
            assembled.append(section)

        return assembled

    def _suggest(self, section: dict) -> str:
        type_map = {"kpi_cards": "KPI card display", "chart": "line/bar chart", "table_chart_combo": "table + bar chart", "text": "text summary"}
        return type_map.get(section.get("type", ""), "bar chart")
