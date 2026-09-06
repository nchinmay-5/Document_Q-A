import pytest

from documents.models import Document
from generation.prompts import NO_EVIDENCE_ANSWER
from generation.query_rewriter import RewrittenQuery
from qa import service
from retrieval.retriever import RetrievalConfig, RetrievalResult
from retrieval.types import RetrievedChunk

pytestmark = pytest.mark.django_db


@pytest.fixture
def indexed_document(user) -> Document:
    return Document.objects.create(
        user=user,
        filename="hr_policy.pdf",
        file="documents/1/hr_policy.pdf",
        content_type="pdf",
        content_hash="a" * 64,
        status=Document.Status.READY,
    )


class _FixedLLM:
    """Returns one scripted answer, so citation handling can be tested exactly."""

    name = "fixed"

    def __init__(self, answer: str):
        self._answer = answer

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._answer


def _fake_retrieval(chunks: list[RetrievedChunk]) -> RetrievalResult:
    return RetrievalResult(
        config=RetrievalConfig(),
        chunks=chunks,
        timings_ms={"retrieval_ms": 1.0},
    )


def _capture_retrieve(monkeypatch, chunks: list[RetrievedChunk]) -> dict:
    """Stand in for retrieval and record the filters it was called with."""
    captured: dict = {}

    def fake_retrieve(query, *, filters, config=None):
        captured["query"] = query
        captured["filters"] = filters
        return _fake_retrieval(chunks)

    monkeypatch.setattr(service, "retrieve", fake_retrieve)
    return captured


def test_answer_is_grounded_in_retrieved_sources(monkeypatch, user, indexed_document):
    chunk = RetrievedChunk(
        chunk_id="doc1_chunk0",
        document_id=indexed_document.id,
        page=12,
        section="Annual Leave",
        text="Employees receive 20 days of annual leave.",
        score=0.8,
        retriever="rrf",
    )
    _capture_retrieve(monkeypatch, [chunk])

    result = service.answer_question(user=user, question="How much annual leave?")

    assert result.provider == "stub"
    assert result.sources[0].filename == "hr_policy.pdf"
    assert result.sources[0].page == 12
    assert result.citations[0].label == "hr_policy.pdf, Page 12"
    assert result.query.rewritten == "How much annual leave?"
    assert result.timings_ms["total_ms"] >= 0


def test_search_is_always_scoped_to_the_asking_user(monkeypatch, user):
    captured = _capture_retrieve(monkeypatch, [])

    service.answer_question(user=user, question="anything at all")

    assert captured["filters"].user_id == user.id


def test_optional_filters_are_forwarded(monkeypatch, user):
    captured = _capture_retrieve(monkeypatch, [])

    service.answer_question(
        user=user, question="anything at all", document_ids=[3], content_types=["pdf"]
    )

    assert captured["filters"].document_ids == [3]
    assert captured["filters"].content_types == ["pdf"]


def test_no_evidence_skips_the_llm_call(monkeypatch, user):
    _capture_retrieve(monkeypatch, [])

    result = service.answer_question(user=user, question="unrelated question")

    assert result.answer == NO_EVIDENCE_ANSWER
    assert result.sources == []
    assert result.timings_ms["generation_ms"] == 0.0


def test_a_follow_up_is_retrieved_with_the_rewritten_query(monkeypatch, user):
    captured = _capture_retrieve(monkeypatch, [])
    monkeypatch.setattr(
        service, "rewrite_query", lambda question, history: RewrittenQuery(
            original=question,
            rewritten="contractor annual leave",
            rewritten_by_llm=True,
            reason="follow-up resolved",
        )
    )

    result = service.answer_question(
        user=user,
        question="What about contractors?",
        history=[{"role": "user", "content": "How much annual leave?"}],
    )

    # Retrieval sees the standalone query; the caller still sees their own.
    assert captured["query"] == "contractor annual leave"
    assert result.question == "What about contractors?"


def test_invented_citation_markers_do_not_reach_the_answer(monkeypatch, user, indexed_document):
    chunk = RetrievedChunk(
        chunk_id="doc1_chunk0",
        document_id=indexed_document.id,
        page=12,
        section="Annual Leave",
        text="Employees receive 20 days of annual leave.",
        score=0.8,
        retriever="reranker",
    )
    _capture_retrieve(monkeypatch, [chunk])
    monkeypatch.setattr(service, "get_llm_client", lambda: _FixedLLM("20 days. [1] Also true. [4]"))

    result = service.answer_question(user=user, question="How much annual leave?")

    assert result.answer == "20 days. [1] Also true."
    assert result.dropped_citations == [4]
