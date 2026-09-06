"""Document read and upload payloads."""
from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """Read-only view of a document and its ingestion state."""

    class Meta:
        model = Document
        fields = [
            "id",
            "filename",
            "content_type",
            "content_hash",
            "status",
            "error_message",
            "page_count",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DocumentUploadSerializer(serializers.Serializer):
    """Validates the uploaded file before anything touches disk."""

    file = serializers.FileField()

    def validate_file(self, uploaded_file):
        extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
        if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            allowed = ", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS)
            raise serializers.ValidationError(f"Unsupported file type '.{extension}'. Allowed: {allowed}.")

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if uploaded_file.size > max_bytes:
            raise serializers.ValidationError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.")
        return uploaded_file
