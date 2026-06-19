"""Report planner — creates report outline and data queries from user request + template."""
import json
from pathlib import Path
from agent.state import AgentState
from prompts.manager import PromptManager
from connectors.llm.base import BaseLLMProvider, Message


class ReportPlanner:
    def __init__(self, prompts: PromptManager, llm: BaseLLMProvider, template_dir: str):
        self.prompts = prompts
        self.llm = llm
        self.template_dir = Path(template_dir)

    def load_template(self, template_name: str) -> dict:
        path = self.template_dir / f"{template_name}.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def plan(self, state: AgentState, template_name: str) -> dict:
        return await self.plan_from_query(
            state["user_query"], template_name,
            schema_context=str(state.get("matched_tables", [])),
            business_context=str(state.get("business_terms", {})),
        )

    async def plan_from_query(self, user_query: str, template_name: str,
                              schema_context: str = "", business_context: str = "") -> dict:
        template = self.load_template(template_name)
        prompt = self.prompts.render("report_plan.j2", {
            "user_query": user_query,
            "template_structure": json.dumps(template, indent=2),
            "schema_context": schema_context,
            "business_context": business_context,
        })
        response = await self.llm.chat([
            Message(role="system", content="You are a report architect. Return JSON with a 'title' and 'outline' array. Each section has 'title', 'type', and 'query' (SQL)."),
            Message(role="user", content=prompt),
        ])
        return json.loads(response.content)
