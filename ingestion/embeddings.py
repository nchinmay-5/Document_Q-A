"""Create embeddings with the configured local Sentence Transformers model."""
import logging
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)


class SentenceTransformerBackend:
    """Local BGE/E5-style model, loaded lazily on first use."""

    def __init__(self, model_name: str, dimensions: int, batch_size: int, query_prefix: str):
        self._model_name = model_name
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._query_prefix = query_prefix
        self._model = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model(self):
        # Deferred import and load keeps Django/Celery start-up fast
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed documents in batches. Vectors are L2-normalised for cosine."""
        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query, with the instruction prefix BGE expects."""
        return self.embed_texts([f"{self._query_prefix}{query}"])[0]

@lru_cache(maxsize=1)
def get_embedding_backend() -> SentenceTransformerBackend:
    """Create and cache the app's one supported embedding backend."""
    if settings.EMBEDDING_BACKEND != "sentence_transformers":
        raise ValueError(
            "Only EMBEDDING_BACKEND='sentence_transformers' is supported."
        )
    return SentenceTransformerBackend(
        model_name=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
        query_prefix=settings.EMBEDDING_QUERY_PREFIX,
    )

