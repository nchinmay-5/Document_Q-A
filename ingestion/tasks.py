"""Document ingestion: the pipeline and the Celery task that drives it.

    parse -> clean -> chunk -> embed -> index

`run_ingestion` is a plain function, so the whole pipeline can be run and
debugged without a broker. The task around it owns only status transitions and
retry policy.
"""
import logging
from dataclasses import dataclass

from celery import shared_task

from documents import services
from documents.models import Document
from ingestion.chunker import chunk_document
from ingestion.cleaner import clean_document
from ingestion.indexer import index_chunks
from ingestion.parser import parse_document
from retrieval.index import delete_document_chunks

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


@dataclass
class IngestionResult:
    document_id: int
    page_count: int
    chunk_count: int

def run_ingestion(document: Document) -> IngestionResult:
    """Run the full pipeline for one document and return what was indexed."""
    parsed = parse_document(document.file_path)
    cleaned = clean_document(parsed)
    logger.info("Parsed document %s into %s pages", document.id, cleaned.page_count)

    chunks = chunk_document(cleaned, document_id=document.id, user_id=document.user_id)
    logger.info("Chunked document %s into %s chunks", document.id, len(chunks))

    # Re-ingestion must not leave stale chunks behind.
    delete_document_chunks(document.id)
    indexed = index_chunks(chunks, content_type=document.content_type)
    logger.info("Indexed %s chunks for document %s", indexed, document.id)

    return IngestionResult(
        document_id=document.id,
        page_count=cleaned.page_count,
        chunk_count=indexed,
    )


@shared_task(
    bind=True,
    name="ingestion.ingest_document",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": MAX_RETRIES},
)
def ingest_document(self, document_id: int) -> dict:
    """Parse, chunk, embed and index one document."""
    document = Document.objects.filter(id=document_id).first()
    if document is None:
        logger.warning("Document %s no longer exists; skipping ingestion", document_id)
        return {"document_id": document_id, "status": "MISSING"}

    services.mark_processing(document)
    try:
        result = run_ingestion(document)
    except Exception as exc:
        # Only give up once Celery has exhausted its retries.
        if self.request.retries >= MAX_RETRIES:
            services.mark_failed(document, f"{type(exc).__name__}: {exc}")
            logger.exception("Ingestion failed permanently for document %s", document_id)
        raise

    services.mark_ready(
        document, page_count=result.page_count, chunk_count=result.chunk_count
    )
    return {
        "document_id": document_id,
        "status": document.status,
        "pages": result.page_count,
        "chunks": result.chunk_count,
    }
