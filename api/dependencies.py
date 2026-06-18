"""Dependency injection for FastAPI — loads config and creates singletons."""
import yaml
from functools import lru_cache
from pathlib import Path
from connectors.llm.deepseek import DeepSeekProvider
from connectors.dw.duckdb import DuckDBConnector
from prompts.manager import PromptManager
from evaluator.rules import SQLEvaluator


@lru_cache()
def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_config() -> dict:
    return load_config()


def get_llm():
    config = load_config()
    llm_cfg = config["llm"]
    default = llm_cfg["default"]
    provider_cfg = llm_cfg["providers"][default]
    return DeepSeekProvider(
        model=provider_cfg["model"],
        api_base=provider_cfg["api_base"],
        api_key=provider_cfg["api_key"],
        temperature=provider_cfg.get("temperature", 0.1),
        max_tokens=provider_cfg.get("max_tokens", 4096),
    )


def get_dw():
    config = load_config()
    dw_cfg = config["dw"]
    if dw_cfg["type"] == "duckdb":
        return DuckDBConnector(dw_cfg["duckdb"]["path"])
    raise ValueError(f"Unsupported DW type: {dw_cfg['type']}")


def get_prompts():
    base = Path(__file__).parent.parent
    return PromptManager(
        template_dir=str(base / "prompts" / "templates"),
        config_path=str(base / "prompts" / "config" / "prompt_config.yaml"),
    )


def get_sql_evaluator():
    config = load_config()
    return SQLEvaluator(max_limit=config["evaluator"]["sql"]["max_limit"])
