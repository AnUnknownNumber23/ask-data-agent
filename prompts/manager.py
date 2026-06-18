from pathlib import Path
from typing import Any
import yaml
from jinja2 import Environment, FileSystemLoader


class PromptManager:
    """Load, version, and render Jinja2 prompt templates."""

    def __init__(self, template_dir: str, config_path: str):
        self.template_dir = Path(template_dir)
        self.config_path = Path(config_path)
        self._env = Environment(loader=FileSystemLoader(str(self.template_dir)))
        self._config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    def render(self, template_name: str, variables: dict[str, Any],
               version: str | None = None) -> str:
        """Render template by name. Uses latest if version not specified."""
        template = self._env.get_template(template_name)
        return template.render(**variables)

    def get_version(self, template_name: str) -> str:
        """Get current version of a template from config."""
        tmpl = self._config.get("templates", {}).get(template_name.replace(".j2", ""), {})
        return tmpl.get("version", "unknown")

    def list_templates(self) -> list[dict[str, Any]]:
        """List all template metadata."""
        result = []
        for name, meta in self._config.get("templates", {}).items():
            result.append({
                "name": f"{name}.j2",
                "version": meta.get("version"),
                "description": meta.get("description"),
                "variables": meta.get("variables", []),
            })
        return result

    def validate(self, template_name: str) -> bool:
        """Check if template exists and has valid syntax."""
        try:
            self._env.get_template(template_name)
            return True
        except Exception:
            return False
