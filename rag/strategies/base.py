from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RAGResult:
    matches: list[dict[str, Any]] = field(default_factory=list)
    strategy_name: str = ""
    confidence: float = 0.0


class BaseRetrieveStrategy(ABC):
    def __init__(self, kbs: dict[str, Any], weights: dict[str, float], top_k: int, threshold: float | None):
        self.kbs = kbs
        self.weights = weights
        self.top_k = top_k
        self.threshold = threshold

    @abstractmethod
    async def execute(self, query: str, context: dict[str, Any]) -> RAGResult:
        ...
