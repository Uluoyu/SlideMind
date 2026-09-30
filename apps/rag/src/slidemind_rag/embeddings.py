"""Local ONNX embeddings, loaded only when the first text is embedded."""

import math
from collections.abc import Iterable
from numbers import Real
from pathlib import Path
from threading import Lock
from typing import Any


def validate_vectors(
    vectors: Iterable[Iterable[float]], expected_count: int, dimensions: int
) -> list[list[float]]:
    """Validate an entire batch and return normalized, JSON-safe float vectors.

    Reject malformed output rather than persisting partial batches or manufacturing
    embeddings. This also provides a shared boundary for injected embedding providers.
    """
    if dimensions <= 0 or expected_count < 0:
        raise ValueError("Embedding dimensions must be positive and count nonnegative")
    try:
        batch = list(vectors)
    except TypeError as exc:
        raise ValueError("Embedding batch must be iterable") from exc
    if len(batch) != expected_count:
        raise ValueError(f"Expected {expected_count} embeddings, received {len(batch)}")
    result = []
    for vector in batch:
        try:
            values = list(vector)
        except TypeError as exc:
            raise ValueError("Each embedding must be a vector") from exc
        if len(values) != dimensions:
            raise ValueError(f"Expected {dimensions} embedding dimensions, received {len(values)}")
        if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
            raise ValueError("Embedding values must be real numbers")
        numbers = [float(value) for value in values]
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("Embedding values must be finite")
        norm = math.hypot(*numbers)
        if norm == 0 or not math.isfinite(norm):
            raise ValueError("Embedding norm must be finite and nonzero")
        result.append([value / norm for value in numbers])
    return result


class FastEmbedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        cache_dir: str | Path | None = None,
        threads: int = 2,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = str(cache_dir) if cache_dir is not None else None
        self._threads = threads
        self._dimensions: int | None = None
        self._model: Any = None
        self._load_lock = Lock()

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            from fastembed import TextEmbedding

            # Metadata lookup does not instantiate ONNX sessions or download weights.
            self._dimensions = TextEmbedding.get_embedding_size(self._model_name)
        return self._dimensions

    def _get_model(self) -> Any:
        with self._load_lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(
                    model_name=self._model_name,
                    cache_dir=self._cache_dir,
                    threads=self._threads,
                )
            return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return validate_vectors(
            self._get_model().embed(texts), expected_count=len(texts), dimensions=self.dimensions
        )

    def embed_query(self, query: str) -> list[float]:
        return validate_vectors(
            self._get_model().query_embed(query), expected_count=1, dimensions=self.dimensions
        )[0]
