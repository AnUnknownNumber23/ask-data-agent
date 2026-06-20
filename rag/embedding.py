"""Embedding functions for ChromaDB — multilingual semantic search."""
import os
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

# Module-level singleton
_sentence_transformer = None


class SentenceTransformerEF(EmbeddingFunction[Documents]):
    """Multilingual MiniLM embedding — 384-dim, 50+ languages, CPU inference."""

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        global _sentence_transformer
        if _sentence_transformer is None:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer = SentenceTransformer(model_name)
        self._model = _sentence_transformer

    def __call__(self, input: Documents) -> Embeddings:
        return self._model.encode(list(input), normalize_embeddings=True).tolist()


def get_embedding_function() -> EmbeddingFunction:
    """Return the embedding function — multilingual MiniLM, cached singleton."""
    return SentenceTransformerEF()
