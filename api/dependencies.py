"""Dependency injection for FastAPI — loads config and creates singletons."""
import os
import yaml
from functools import lru_cache
from pathlib import Path
from connectors.dw.duckdb import DuckDBConnector
from prompts.manager import PromptManager
from evaluator.rules import SQLEvaluator
from rag.knowledge.schema_kb import SchemaKB
from rag.knowledge.business_kb import BusinessKB
from rag.knowledge.fix_kb import FixKB
from rag.knowledge.analytics_kb import AnalyticsKB
from rag.router import RAGRouter

_rag_router: RAGRouter | None = None

# Provider → env var mapping (keys are NEVER in config.yaml)
_API_KEY_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "QWEN_API_KEY",
    "glm": "GLM_API_KEY",
}


@lru_cache()
def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_config() -> dict:
    return load_config()


def get_llm():
    # Dev mode: use mock LLM when no real API key available
    if os.environ.get("MOCK_LLM", "").lower() in ("true", "1", "yes"):
        from tests.fixtures.mock_llm import MockLLM
        return MockLLM()

    config = load_config()
    llm_cfg = config["llm"]
    default = llm_cfg["default"]
    provider_cfg = llm_cfg["providers"][default]
    provider_type = default

    # API key from environment variable only — never from config file
    env_var = _API_KEY_ENV_VARS.get(provider_type)
    api_key = os.environ.get(env_var, "") if env_var else ""
    if not api_key:
        raise RuntimeError(
            f"Missing API key for '{provider_type}'. "
            f"Set the {env_var} environment variable, or use MOCK_LLM=true for dev mode."
        )

    if provider_type == "deepseek":
        from connectors.llm.deepseek import DeepSeekProvider
        return DeepSeekProvider(
            model=provider_cfg["model"],
            api_base=provider_cfg["api_base"],
            api_key=api_key,
            temperature=provider_cfg.get("temperature", 0.1),
            max_tokens=provider_cfg.get("max_tokens", 4096),
        )
    elif provider_type == "qwen":
        from connectors.llm.qwen import QwenProvider
        return QwenProvider(
            model=provider_cfg["model"],
            api_base=provider_cfg["api_base"],
            api_key=api_key,
        )
    elif provider_type == "glm":
        from connectors.llm.glm import GLMProvider
        return GLMProvider(
            model=provider_cfg["model"],
            api_base=provider_cfg["api_base"],
            api_key=api_key,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_type}")


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


async def get_rag() -> RAGRouter | None:
    global _rag_router
    if _rag_router is not None:
        return _rag_router

    import asyncio
    config = load_config()
    chroma_path = config["rag"]["chromadb"]["path"]

    async def _init_rag():
        # Initialize knowledge bases
        dw = get_dw()
        schema_kb = SchemaKB(dw, chroma_path)
        business_kb = BusinessKB(chroma_path)
        fix_kb = FixKB(chroma_path)
        analytics_kb = AnalyticsKB(chroma_path)

        # Sync/seed
        try:
            await schema_kb.sync()
        except Exception as e:
            print(f"SchemaKB sync warning: {e}")

        try:
            business_kb.seed_defaults()
        except Exception as e:
            print(f"BusinessKB seed warning: {e}")

        try:
            fix_kb.seed_defaults()
        except Exception as e:
            print(f"FixKB seed warning: {e}")

        try:
            analytics_kb.seed_defaults()
        except Exception as e:
            print(f"AnalyticsKB seed warning: {e}")

        kbs = {
            "schema_kb": schema_kb,
            "business_kb": business_kb,
            "fix_kb": fix_kb,
            "analytics_kb": analytics_kb,
        }
        return RAGRouter(kbs=kbs, config=config["rag"]["retrieval"])

    try:
        _rag_router = await asyncio.wait_for(_init_rag(), timeout=120)
        return _rag_router
    except asyncio.TimeoutError:
        print("RAG initialization timed out (ChromaDB model download may be in progress). "
              "Agent will run without RAG. RAG will be retried on next request.")
        return None
    except Exception as e:
        print(f"RAG initialization failed: {e}. Agent will run without RAG.")
        return None
