"""The single result shape every retriever returns."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: int
    page: int
    section: str
    text: str
    score: float
    retriever: str  # dense | bm25 | rrf

    @classmethod
    def from_hit(cls, hit: dict, retriever: str) -> "RetrievedChunk":
        """Build from an Elasticsearch hit."""
        source = hit["_source"]
        return cls(
            chunk_id=source["chunk_id"],
            document_id=source["document_id"],
            page=source.get("page", 0),
            section=source.get("section", ""),
            text=source.get("text", ""),
            score=float(hit.get("_score") or 0.0),
            retriever=retriever,
        )

    def with_score(self, score: float, retriever: str) -> "RetrievedChunk":
        """Copy carrying a new score, used when stages re-rank results."""
        return replace(self, score=score, retriever=retriever)

    def describe(self) -> dict:
        """Serialisable form for API debug output."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "page": self.page,
            "section": self.section,
            "score": round(self.score, 6),
            "retriever": self.retriever,
            "text": self.text,
        }
