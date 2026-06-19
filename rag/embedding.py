"""Lightweight embedding functions that don't require model downloads.

ChromaDB defaults to all-MiniLM-L6-v2 (79MB ONNX model) which downloads on first use.
For environments with slow/unreliable internet, we provide a fallback that allows the
agent to start immediately. Keyword and metadata search still work; only vector similarity
is degraded.
"""
import hashlib
import os
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic hash-based embeddings — no model download needed.

    Uses SHA-256 to produce 384-dim embedding vectors from document text.
    This allows ChromaDB to store and retrieve documents without downloading
    a sentence-transformer model. Semantic quality is low, but the system
    relies heavily on keyword and metadata search (see config weights),
    so overall RAG quality remains acceptable for development.
    """

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            # Deterministic hash → 384 float32 values (matches MiniLM-L6-V2 dim)
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # Extend to 384 dims by repeated hashing
            vec = []
            seed = h
            while len(vec) < 384:
                for b in seed:
                    vec.append((b / 255.0) * 2.0 - 1.0)
                    if len(vec) >= 384:
                        break
                if len(vec) < 384:
                    seed = hashlib.sha256(seed).digest()
            embeddings.append(vec[:384])
        return embeddings


# Module-level singleton
_hash_ef = None


def get_embedding_function() -> EmbeddingFunction:
    """Return the best available embedding function.

    Tries to use the default ONNX model if already cached, otherwise falls
    back to hash-based embeddings to avoid blocking on a 79MB download.
    """
    global _hash_ef

    # Check if the ONNX model is already cached
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "chroma", "onnx_models", "all-MiniLM-L6-v2")
    if os.path.isdir(cache_dir) and any(f.endswith(".onnx") for f in os.listdir(cache_dir)):
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            return ONNXMiniLM_L6_V2()
        except Exception:
            pass

    # Fallback: use hash-based embeddings (no download needed)
    if _hash_ef is None:
        _hash_ef = HashEmbeddingFunction()
    return _hash_ef
