"""Cross-encoder reranking of retrieval candidates.

Fusion orders candidates by rank agreement; it never reads the query and a
passage together. A cross-encoder does, which is why it is worth one extra
model call over a short candidate list.

Only the local sentence-transformers backend exists today. Adding a hosted
reranker means adding a class and one entry to _BACKENDS.
"""
import logging
from functools import lru_cache
from typing import Protocol

from django.conf import settings

from retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

RERANKER_NAME = "reranker"


class RerankerBackend(Protocol):
    """What the pipeline needs from a reranker: one relevance score per passage."""

    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderBackend:
    """Local cross-encoder (BGE reranker family), loaded lazily on first use."""

    def __init__(self, model_name: str, batch_size: int):
        self._model_name = model_name
        self._batch_size = batch_size
        self._model = None

    @property
    def model(self):
        # Deferred import and load, for the same reason as the embedding
        # backend: fast start-up, and unit tests that never import torch.
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model %s", self._model_name)
            self._model = CrossEncoder(self._model_name)
        return self._model

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Score every (query, passage) pair in one batched forward pass."""
        if not passages:
            return []
        scores = self.model.predict(
            [(query, passage) for passage in passages],
            batch_size=self._batch_size,
            show_progress_bar=False,
        )
        return [float(score) for score in scores]


class IdentityReranker:
    """Keeps the incoming order, for offline development and tests.

    Scores descend with position, so downstream code sees a well-formed ranking
    without a model download.
    """

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(len(passages) - index) for index in range(len(passages))]


def _build_cross_encoder_backend() -> CrossEncoderBackend:
    return CrossEncoderBackend(
        model_name=settings.RERANKER_MODEL,
        batch_size=settings.RERANKER_BATCH_SIZE,
    )


_BACKENDS = {
    "cross_encoder": _build_cross_encoder_backend,
    "identity": IdentityReranker,
}


@lru_cache(maxsize=1)
def get_reranker() -> RerankerBackend:
    """The configured backend, cached so the model loads at most once."""
    name = settings.RERANKER_BACKEND
    builder = _BACKENDS.get(name)
    if builder is None:
        supported = ", ".join(sorted(_BACKENDS))
        raise ValueError(f"Unknown RERANKER_BACKEND '{name}'. Supported: {supported}.")
    return builder()


def rerank(query: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    """Re-score candidates against the query and return the best `top_k`."""
    if not chunks:
        return []

    scores = get_reranker().score(query, [chunk.text for chunk in chunks])
    rescored = [chunk.with_score(score, RERANKER_NAME) for chunk, score in zip(chunks, scores)]
    rescored.sort(key=lambda chunk: chunk.score, reverse=True)
    return rescored[:top_k]
