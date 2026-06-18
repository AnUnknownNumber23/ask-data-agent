"""Report renderer — formats assembled sections into the final JSON payload."""
from datetime import datetime, timezone


class ReportRenderer:
    def render(self, title: str, sections: list[dict]) -> dict:
        return {
            "report_id": f"rpt_{int(datetime.now(timezone.utc).timestamp())}",
            "title": title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections,
            "export_formats": ["pdf", "excel"],
        }
