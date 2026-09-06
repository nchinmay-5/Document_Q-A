"""Document lifecycle operations shared by the API and the ingestion worker."""
import hashlib
import logging
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from documents.models import Document

logger = logging.getLogger(__name__)

HASH_READ_SIZE = 1024 * 1024


def compute_content_hash(uploaded_file: UploadedFile) -> str:
    """SHA-256 of the upload, streamed so large files stay off the heap."""
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks(HASH_READ_SIZE):
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def detect_content_type(filename: str) -> str:
    """Normalised document type ('pdf', 'docx', 'txt') used for filtering."""
    return Path(filename).suffix.lower().lstrip(".")


def create_document(user: User, uploaded_file: UploadedFile) -> Document:
    """Persist an upload and hand it to the ingestion worker."""
    document = Document.objects.create(
        user=user,
        filename=uploaded_file.name,
        file=uploaded_file,
        content_type=detect_content_type(uploaded_file.name),
        content_hash=compute_content_hash(uploaded_file),
        status=Document.Status.UPLOADED,
    )
    queue_ingestion(document)
    return document


def queue_ingestion(document: Document) -> None:
    """Queue background ingestion for a document."""
    # Imported here because ingestion.tasks imports this module.
    from ingestion.tasks import ingest_document

    ingest_document.delay(document.id)
    logger.info("Queued ingestion for document %s", document.id)


def delete_document(document: Document) -> None:
    """Remove a document's indexed chunks, its file, and its record."""
    from retrieval.index import delete_document_chunks

    delete_document_chunks(document.id)
    document.file.delete(save=False)
    document.delete()


def mark_processing(document: Document) -> None:
    document.status = Document.Status.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])


def mark_ready(document: Document, *, page_count: int, chunk_count: int) -> None:
    document.status = Document.Status.READY
    document.error_message = ""
    document.page_count = page_count
    document.chunk_count = chunk_count
    document.save(
        update_fields=["status", "error_message", "page_count", "chunk_count", "updated_at"]
    )


def mark_failed(document: Document, error: str) -> None:
    document.status = Document.Status.FAILED
    document.error_message = error[:2000]
    document.save(update_fields=["status", "error_message", "updated_at"])
