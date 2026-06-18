from enum import Enum
from typing import Any
from .strategies.base import BaseRetrieveStrategy, RAGResult
from .strategies.understand import SemanticDiscoveryStrategy
from .strategies.reason import ContextSupplementStrategy
from .strategies.reflect import ExactCorrectionStrategy
from .strategies.analyze import DomainKnowledgeStrategy


class Stage(Enum):
    UNDERSTAND = "understand"
    REASON = "reason"
    REFLECT = "reflect"
    ANALYZE = "analyze"


class RAGRouter:
    """Dispatch retrieval to the correct strategy based on agent stage."""

    def __init__(self, kbs: dict[str, Any], config: dict[str, Any]):
        self.kbs = kbs
        self.config = config
        self._strategies: dict[Stage, BaseRetrieveStrategy] = {}

    def _get_strategy(self, stage: Stage) -> BaseRetrieveStrategy:
        if stage not in self._strategies:
            cfg = self.config.get(stage.value, {})
            weights = {
                "vector": cfg.get("vector_weight", 0.3),
                "keyword": cfg.get("keyword_weight", 0.3),
                "meta": cfg.get("meta_weight", 0.3),
            }
            top_k = cfg.get("top_k", 5)
            threshold = cfg.get("threshold", None)
            match stage:
                case Stage.UNDERSTAND:
                    self._strategies[stage] = SemanticDiscoveryStrategy(self.kbs, weights, top_k, threshold)
                case Stage.REASON:
                    self._strategies[stage] = ContextSupplementStrategy(self.kbs, weights, top_k, threshold)
                case Stage.REFLECT:
                    self._strategies[stage] = ExactCorrectionStrategy(self.kbs, weights, top_k, threshold)
                case Stage.ANALYZE:
                    self._strategies[stage] = DomainKnowledgeStrategy(self.kbs, weights, top_k, threshold)
        return self._strategies[stage]

    async def retrieve(self, stage: Stage, query: str, context: dict[str, Any]) -> RAGResult:
        strategy = self._get_strategy(stage)
        return await strategy.execute(query, context)
