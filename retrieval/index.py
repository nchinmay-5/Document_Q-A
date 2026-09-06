"""The Elasticsearch chunk store: connection, index definition, maintenance.

The index is the single source of truth for chunk text, vectors and metadata;
Postgres only tracks documents and their status.
"""
import logging
from functools import lru_cache

from django.conf import settings
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> Elasticsearch:
    """One connection pool for the whole process."""
    basic_auth = None
    if settings.ELASTICSEARCH_USERNAME:
        basic_auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

    return Elasticsearch(
        settings.ELASTICSEARCH_URL,
        basic_auth=basic_auth,
        request_timeout=settings.ELASTICSEARCH_REQUEST_TIMEOUT,
    )

# Fields every retriever reads back for a hit (the vector is never returned).
SOURCE_FIELDS = ["chunk_id", "document_id", "chunk_index", "page", "section", "text", "content_type"]


def chunk_index_name() -> str:
    return settings.ELASTICSEARCH_CHUNK_INDEX


def chunk_index_settings() -> dict:
    """Mapping for the chunk index: BM25 on `text`, kNN on `embedding`.

    document_id and user_id are numeric so filter terms never depend on string
    conversion.
    """
    return {
        "mappings": {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "document_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "chunk_index": {"type": "integer"},
                "page": {"type": "integer"},
                "section": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
                "text": {"type": "text", "analyzer": "english"},
                "content_type": {"type": "keyword"},
                "created_at": {"type": "date"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": settings.EMBEDDING_DIMENSIONS,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }
    }


def ensure_index() -> None:
    """Create the chunk index if it does not exist yet."""
    client = get_client()
    name = chunk_index_name()
    if not client.indices.exists(index=name):
        client.indices.create(index=name, **chunk_index_settings())
        logger.info("Created Elasticsearch index %s", name)


def delete_document_chunks(document_id: int) -> int:
    """Remove every chunk belonging to a document. Safe to call repeatedly."""
    client = get_client()
    name = chunk_index_name()
    if not client.indices.exists(index=name):
        return 0

    response = client.delete_by_query(
        index=name,
        query={"term": {"document_id": document_id}},
        refresh=True,
        conflicts="proceed",
    )
    deleted = int(response.get("deleted", 0))
    if deleted:
        logger.info("Deleted %s chunks for document %s", deleted, document_id)
    return deleted


def count_document_chunks(document_id: int) -> int:
    """Indexed chunk count for a document, used by tests and diagnostics."""
    client = get_client()
    name = chunk_index_name()
    if not client.indices.exists(index=name):
        return 0
    return int(client.count(index=name, query={"term": {"document_id": document_id}})["count"])
