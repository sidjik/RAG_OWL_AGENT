"""Optional embeddings adapter. The default server needs no model downloads."""

from typing import Protocol

import numpy as np


class Encoder(Protocol):
    model_id: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEncoder:
    def __init__(self, model_id: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install semantic search with: uv sync --extra semantic") from exc
        self.model_id = model_id
        self._model = SentenceTransformer(model_id)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )


def unit_vectors(vectors: np.ndarray, rows: int) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != rows or matrix.shape[1] == 0:
        raise ValueError("Embedding provider returned an invalid matrix shape")
    if not np.isfinite(matrix).all():
        raise ValueError("Embedding provider returned non-finite values")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(norms).all():
        raise ValueError("Embedding provider returned invalid vector magnitudes")
    if (norms == 0).any():
        raise ValueError("Embedding provider returned a zero vector")
    return matrix / norms
