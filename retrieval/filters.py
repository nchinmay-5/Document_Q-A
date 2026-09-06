"""Metadata filters applied before any search runs.

`user_id` is a required constructor argument, so it is not possible to build a
query that reaches another user's chunks.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SearchFilters:
    user_id: int
    document_ids: list[int] | None = None
    created_after: datetime | None = None
    content_types: list[str] | None = None

    def to_es_filters(self) -> list[dict]:
        """Translate to Elasticsearch filter clauses (no scoring impact)."""
        clauses: list[dict] = [{"term": {"user_id": self.user_id}}]

        if self.document_ids:
            clauses.append({"terms": {"document_id": list(self.document_ids)}})
        if self.content_types:
            clauses.append({"terms": {"content_type": list(self.content_types)}})
        if self.created_after:
            clauses.append({"range": {"created_at": {"gte": self.created_after.isoformat()}}})

        return clauses

    def describe(self) -> dict:
        """Serialisable summary for debug output and, later, traces."""
        return {
            "user_id": self.user_id,
            "document_ids": list(self.document_ids) if self.document_ids else None,
            "content_types": list(self.content_types) if self.content_types else None,
            "created_after": self.created_after.isoformat() if self.created_after else None,
        }
