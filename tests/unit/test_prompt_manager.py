import pytest
import tempfile
from pathlib import Path
from prompts.manager import PromptManager


class TestPromptManager:
    @pytest.fixture
    def manager(self, tmp_path):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "test.j2").write_text("Hello {{ name }}!")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "prompt_config.yaml"
        config_path.write_text("""
templates:
  test:
    version: "1.0.0"
    description: "A test template"
    variables:
      - name
""")
        return PromptManager(str(templates_dir), str(config_path))

    def test_render_template(self, manager):
        result = manager.render("test.j2", {"name": "World"})
        assert result == "Hello World!"

    def test_get_version(self, manager):
        assert manager.get_version("test.j2") == "1.0.0"

    def test_list_templates(self, manager):
        templates = manager.list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "test.j2"

    def test_validate_existing(self, manager):
        assert manager.validate("test.j2") is True

    def test_validate_missing(self, manager):
        assert manager.validate("nonexistent.j2") is False
