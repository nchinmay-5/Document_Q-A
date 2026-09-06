"""The Document record and its ingestion lifecycle."""
import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models


def document_upload_path(instance: "Document", filename: str) -> str:
    """Store uploads under media/documents/<user_id>/<uuid><ext>."""
    suffix = Path(filename).suffix.lower()
    return f"documents/{instance.user_id}/{uuid.uuid4().hex}{suffix}"


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    content_type = models.CharField(max_length=16)
    content_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True, default="")
    page_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # Supports the per-user duplicate lookup a later phase will add.
        indexes = [models.Index(fields=["user", "content_hash"])]

    def __str__(self) -> str:
        return f"{self.filename} ({self.status})"

    @property
    def file_path(self) -> str:
        """Absolute path on disk, as the ingestion pipeline expects."""
        return self.file.path
