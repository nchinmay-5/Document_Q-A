import pytest

from retrieval import bm25, dense, retriever
from retrieval.filters import SearchFilters
from retrieval.retriever import (
    MODE_BM25,
    MODE_DENSE,
    MODE_HYBRID,
    RetrievalConfig,
    retrieve,
)
from retrieval.types import RetrievedChunk


def _chunk(chunk_id: str, retriever_name: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=1,
        page=1,
        section="Body",
        text=chunk_id,
        score=1.0,
        retriever=retriever_name,
    )


@pytest.fixture
def fake_searches(monkeypatch):
    """Replace both retrievers so no Elasticsearch instance is needed."""
    calls: dict[str, int] = {"dense": 0, "bm25": 0}

    def fake_dense(query, *, filters, top_k):
        calls["dense"] += 1
        return [_chunk("d1", "dense"), _chunk("shared", "dense")]

    def fake_bm25(query, *, filters, top_k):
        calls["bm25"] += 1
        return [_chunk("shared", "bm25"), _chunk("b1", "bm25")]

    monkeypatch.setattr(dense, "search", fake_dense)
    monkeypatch.setattr(bm25, "search", fake_bm25)
    return calls


FILTERS = SearchFilters(user_id=1)


def test_dense_mode_skips_bm25(fake_searches):
    result = retrieve("leave policy", filters=FILTERS, config=RetrievalConfig(mode=MODE_DENSE))

    assert fake_searches == {"dense": 1, "bm25": 0}
    assert [chunk.chunk_id for chunk in result.chunks] == ["d1", "shared"]
    assert result.fused_results == []


def test_bm25_mode_skips_dense(fake_searches):
    result = retrieve("leave policy", filters=FILTERS, config=RetrievalConfig(mode=MODE_BM25))

    assert fake_searches == {"dense": 0, "bm25": 1}
    assert [chunk.chunk_id for chunk in result.chunks] == ["shared", "b1"]


def test_hybrid_mode_runs_both_and_fuses(fake_searches):
    result = retrieve("leave policy", filters=FILTERS, config=RetrievalConfig(mode=MODE_HYBRID))

    assert fake_searches == {"dense": 1, "bm25": 1}
    # "shared" is ranked by both retrievers, so RRF puts it first.
    assert result.chunks[0].chunk_id == "shared"
    assert result.chunks[0].retriever == "rrf"
    assert set(result.timings_ms) == {"dense_ms", "bm25_ms", "fusion_ms", "retrieval_ms"}


def test_final_k_truncates_results(fake_searches):
    result = retrieve(
        "leave policy", filters=FILTERS, config=RetrievalConfig(mode=MODE_HYBRID, final_k=1)
    )

    assert len(result.chunks) == 1


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        RetrievalConfig(mode="magic")


def test_config_from_settings_applies_overrides(settings):
    settings.RETRIEVAL_MODE = MODE_DENSE
    settings.RETRIEVAL_FINAL_K = 20

    config = RetrievalConfig.from_settings(mode=None, final_k=5)

    assert config.mode == MODE_DENSE
    assert config.final_k == 5


def test_reranking_is_the_last_ordering_stage(fake_searches, monkeypatch):
    """The reranker sees the fused candidates and produces the final chunks."""
    seen: dict = {}

    def fake_rerank(query, chunks, *, top_k):
        seen["candidates"] = [chunk.chunk_id for chunk in chunks]
        return [chunk.with_score(1.0, "reranker") for chunk in reversed(chunks)][:top_k]

    monkeypatch.setattr(retriever, "rerank", fake_rerank)

    result = retrieve(
        "leave policy",
        filters=FILTERS,
        config=RetrievalConfig(mode=MODE_HYBRID, rerank=True, rerank_k=2),
    )

    assert seen["candidates"][0] == "shared"  # what RRF produced
    assert len(result.chunks) == 2
    assert result.chunks == result.reranked_results
    assert result.chunks[0].retriever == "reranker"
    assert "rerank_ms" in result.timings_ms


def test_reranking_off_leaves_the_fused_order(fake_searches, monkeypatch):
    monkeypatch.setattr(retriever, "rerank", lambda *args, **kwargs: pytest.fail("not called"))

    result = retrieve(
        "leave policy", filters=FILTERS, config=RetrievalConfig(mode=MODE_HYBRID, rerank=False)
    )

    assert result.reranked_results == []
    assert result.chunks[0].retriever == "rrf"


def test_config_label_names_the_configuration():
    assert RetrievalConfig(mode=MODE_HYBRID, rerank=True).label == "hybrid+reranker"
    assert RetrievalConfig(mode=MODE_DENSE, rerank=False).label == "dense"
