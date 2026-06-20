"""Embedding functions for ChromaDB — multilingual semantic search."""
import os
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

# Module-level singleton
_sentence_transformer = None


class SentenceTransformerEF(EmbeddingFunction[Documents]):
    """Multilingual MiniLM embedding — 384-dim, 50+ languages, CPU inference."""

    @staticmethod
    def name() -> str:
        return "paraphrase-multilingual-MiniLM-L12-v2"

    def __call__(self, input: Documents) -> Embeddings:
        global _sentence_transformer
        if _sentence_transformer is None:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return _sentence_transformer.encode(list(input), normalize_embeddings=True).tolist()


def get_embedding_function() -> EmbeddingFunction:
    """Return the embedding function — multilingual MiniLM, cached singleton."""
    return SentenceTransformerEF()
