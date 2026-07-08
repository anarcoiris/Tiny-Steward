"""Embedding client for Nomic via Ollama API.

Talks to Nomic on :11438 via /api/embeddings (Ollama native).
Provides embed(), embed_batch(), and cosine_similarity().
"""

from __future__ import annotations

import numpy as np
import httpx


class Embedder:
    """Client for Nomic embeddings via Ollama's /api/embeddings endpoint."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11438",
        model: str = "nomic-embed-text",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string. Returns a 1-D float32 array."""
        resp = self._client.post(
            "/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return np.array(data["embedding"], dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed multiple texts. Returns a 2-D array (n_texts, dim).

        Ollama's /api/embeddings doesn't natively batch, so we
        call sequentially. For index-building this is fine.
        """
        vectors = []
        for text in texts:
            vectors.append(self.embed(text))
        return np.stack(vectors)

    def health(self) -> bool:
        """Check if the embedding endpoint is reachable."""
        try:
            resp = self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ------------------------------------------------------------------
# Vector math utilities
# ------------------------------------------------------------------

def cosine_similarity(query: np.ndarray, index: np.ndarray) -> np.ndarray:
    """Cosine similarity between a query vector and an index matrix.

    Args:
        query: 1-D array (dim,)
        index: 2-D array (n_skills, dim)

    Returns:
        1-D array (n_skills,) of similarity scores in [-1, 1].
    """
    # Normalize
    q_norm = query / (np.linalg.norm(query) + 1e-10)
    idx_norms = np.linalg.norm(index, axis=1, keepdims=True) + 1e-10
    idx_normalized = index / idx_norms
    return idx_normalized @ q_norm
