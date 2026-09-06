from django.contrib import admin

from documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "filename", "user", "status", "chunk_count", "created_at"]
    list_filter = ["status", "content_type"]
    search_fields = ["filename", "content_hash"]
