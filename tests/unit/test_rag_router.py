import pytest
from rag.router import RAGRouter, Stage


class TestRAGRouter:
    @pytest.fixture
    def router(self):
        config = {
            "understand": {"vector_weight": 0.6, "keyword_weight": 0.3, "meta_weight": 0.1, "top_k": 5, "threshold": 0.65},
            "reason": {"vector_weight": 0.3, "keyword_weight": 0.2, "meta_weight": 0.5, "top_k": 8, "threshold": 0.5},
            "reflect": {"vector_weight": 0.0, "keyword_weight": 0.6, "meta_weight": 0.4, "top_k": 3, "threshold": None},
            "analyze": {"vector_weight": 0.7, "keyword_weight": 0.0, "meta_weight": 0.3, "top_k": 3, "threshold": 0.7},
        }
        return RAGRouter(kbs={}, config=config)

    def test_understand_strategy_type(self, router):
        from rag.strategies.understand import SemanticDiscoveryStrategy
        strategy = router._get_strategy(Stage.UNDERSTAND)
        assert isinstance(strategy, SemanticDiscoveryStrategy)

    def test_reflect_strategy_has_zero_vector(self, router):
        strategy = router._get_strategy(Stage.REFLECT)
        assert strategy.weights["vector"] == 0.0
        assert strategy.weights["keyword"] == 0.6

    def test_reason_strategy_meta_weight(self, router):
        strategy = router._get_strategy(Stage.REASON)
        assert strategy.weights["meta"] == 0.5
        assert strategy.top_k == 8

    def test_analyze_threshold(self, router):
        strategy = router._get_strategy(Stage.ANALYZE)
        assert strategy.threshold == 0.7
