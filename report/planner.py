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
        with open(path, "r") as f:
            return json.load(f)

    async def plan(self, state: AgentState, template_name: str) -> dict:
        template = self.load_template(template_name)
        prompt = self.prompts.render("report_plan.j2", {
            "user_query": state["user_query"],
            "template_structure": json.dumps(template, indent=2),
            "schema_context": str(state.get("matched_tables", [])),
            "business_context": str(state.get("business_terms", {})),
        })
        response = await self.llm.chat([
            Message(role="system", content="You are a report architect. Return JSON with an 'outline' array."),
            Message(role="user", content=prompt),
        ])
        return json.loads(response.content)
