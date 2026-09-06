"""Embed chunks and bulk-write them to Elasticsearch."""
import logging
from datetime import datetime, timezone

from elasticsearch.helpers import bulk

from ingestion.chunker import Chunk
from ingestion.embeddings import get_embedding_backend
from retrieval.index import chunk_index_name, ensure_index, get_client

logger = logging.getLogger(__name__)


def _to_bulk_action(chunk: Chunk, embedding: list[float], content_type: str, indexed_at: str) -> dict:
    return {
        "_index": chunk_index_name(),
        "_id": chunk.chunk_id,  # deterministic id makes re-indexing idempotent
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "user_id": chunk.user_id,
        "chunk_index": chunk.chunk_index,
        "page": chunk.page,
        "section": chunk.section,
        "text": chunk.text,
        "content_type": content_type,
        "created_at": indexed_at,
        "embedding": embedding,
    }


def index_chunks(chunks: list[Chunk], *, content_type: str) -> int:
    """Index chunks with their embeddings; returns how many were written."""
    if not chunks:
        return 0

    ensure_index()
    embeddings = get_embedding_backend().embed_texts([chunk.text for chunk in chunks])
    indexed_at = datetime.now(timezone.utc).isoformat()

    actions = [
        _to_bulk_action(chunk, embedding, content_type, indexed_at)
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    # refresh=True so a document is searchable the moment ingestion completes.
    written, errors = bulk(get_client(), actions, refresh=True, raise_on_error=True)
    if errors:
        logger.error("Bulk indexing reported errors: %s", errors)
    return written
