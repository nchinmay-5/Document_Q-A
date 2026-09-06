import pytest

from reranking import reranker
from reranking.reranker import IdentityReranker, RERANKER_NAME, rerank
from retrieval.types import RetrievedChunk


def _chunk(chunk_id: str, text: str, score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=1,
        page=1,
        section="Body",
        text=text,
        score=score,
        retriever="rrf",
    )


class ScriptedReranker:
    """Returns a fixed score per passage, keyed by its text."""

    def __init__(self, scores: dict[str, float]):
        self._scores = scores

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [self._scores[passage] for passage in passages]


@pytest.fixture
def scripted(monkeypatch):
    def install(scores: dict[str, float]):
        monkeypatch.setattr(reranker, "get_reranker", lambda: ScriptedReranker(scores))

    return install


def test_reranking_reorders_by_cross_encoder_score(scripted):
    scripted({"weak": 0.1, "strong": 0.9})

    ranked = rerank("query", [_chunk("c1", "weak"), _chunk("c2", "strong")], top_k=5)

    assert [chunk.chunk_id for chunk in ranked] == ["c2", "c1"]
    assert ranked[0].score == 0.9
    assert ranked[0].retriever == RERANKER_NAME


def test_top_k_truncates_to_the_best_candidates(scripted):
    scripted({"a": 0.1, "b": 0.5, "c": 0.9})

    ranked = rerank("query", [_chunk("c1", "a"), _chunk("c2", "b"), _chunk("c3", "c")], top_k=2)

    assert [chunk.chunk_id for chunk in ranked] == ["c3", "c2"]


def test_no_candidates_skips_the_model(monkeypatch):
    monkeypatch.setattr(
        reranker, "get_reranker", lambda: pytest.fail("the model must not be loaded")
    )

    assert rerank("query", [], top_k=5) == []


def test_identity_backend_preserves_input_order():
    scores = IdentityReranker().score("query", ["first", "second", "third"])

    assert scores == sorted(scores, reverse=True)


def test_unknown_backend_is_rejected(settings):
    settings.RERANKER_BACKEND = "magic"
    reranker.get_reranker.cache_clear()

    with pytest.raises(ValueError):
        reranker.get_reranker()

    reranker.get_reranker.cache_clear()
