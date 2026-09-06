import pytest

from retrieval.fusion import FUSED_RETRIEVER_NAME, reciprocal_rank_fusion
from retrieval.types import RetrievedChunk


def _chunk(chunk_id: str, score: float = 1.0, retriever: str = "dense") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=1,
        page=1,
        section="Body",
        text=f"text of {chunk_id}",
        score=score,
        retriever=retriever,
    )


def test_chunk_found_by_both_retrievers_ranks_first():
    dense = [_chunk("a"), _chunk("b"), _chunk("c")]
    bm25 = [_chunk("c", retriever="bm25"), _chunk("a", retriever="bm25")]

    fused = reciprocal_rank_fusion([dense, bm25], k=60)

    assert fused[0].chunk_id == "a"  # ranks 1 and 2
    assert fused[1].chunk_id == "c"  # ranks 3 and 1
    assert fused[-1].chunk_id == "b"  # rank 2 in one list only


def test_scores_follow_the_rrf_formula():
    fused = reciprocal_rank_fusion([[_chunk("a")], [_chunk("a", retriever="bm25")]], k=60)

    assert fused[0].score == pytest.approx(2 / 61)
    assert fused[0].retriever == FUSED_RETRIEVER_NAME


def test_results_are_deduplicated_and_truncated():
    dense = [_chunk("a"), _chunk("b")]
    bm25 = [_chunk("b", retriever="bm25"), _chunk("a", retriever="bm25")]

    fused = reciprocal_rank_fusion([dense, bm25], k=60, top_k=1)

    assert len(fused) == 1


def test_empty_input_returns_empty_list():
    assert reciprocal_rank_fusion([[], []], k=60) == []
