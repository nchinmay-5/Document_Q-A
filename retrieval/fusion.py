"""Reciprocal Rank Fusion.

RRF merges ranked lists using positions rather than scores, which avoids having
to normalise BM25 scores against cosine similarities:

    score(chunk) = sum over lists of 1 / (k + rank)
"""
from retrieval.types import RetrievedChunk

FUSED_RETRIEVER_NAME = "rrf"


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
    *,
    k: int = 60,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Fuse ranked result lists into one list ordered by RRF score."""
    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
            chunks.setdefault(chunk.chunk_id, chunk)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    fused = [
        chunks[chunk_id].with_score(score, FUSED_RETRIEVER_NAME) for chunk_id, score in ordered
    ]
    return fused[:top_k] if top_k else fused
