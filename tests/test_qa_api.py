import pytest

from generation.llm import LLMError
from generation.query_rewriter import RewrittenQuery
from qa import views
from qa.service import AnswerResult
from retrieval.filters import SearchFilters
from retrieval.retriever import RetrievalConfig, RetrievalResult
from retrieval.types import RetrievedChunk

pytestmark = pytest.mark.django_db

ASK_URL = "/api/qa/ask/"


def _answer_result(question: str) -> AnswerResult:
    chunk = RetrievedChunk(
        chunk_id="doc1_chunk0",
        document_id=1,
        page=4,
        section="Annual Leave",
        text="20 days of annual leave.",
        score=0.5,
        retriever="rrf",
    )
    return AnswerResult(
        question=question,
        answer="20 days. [1]",
        provider="stub",
        query=RewrittenQuery(
            original=question, rewritten=question, rewritten_by_llm=False, reason="no history"
        ),
        sources=[],
        citations=[],
        filters=SearchFilters(user_id=1),
        retrieval=RetrievalResult(
            config=RetrievalConfig(),
            chunks=[chunk],
            dense_results=[chunk],
            bm25_results=[chunk],
            fused_results=[chunk],
            timings_ms={"retrieval_ms": 2.0},
        ),
        timings_ms={"total_ms": 5.0},
    )


def test_ask_returns_answer_and_configuration(api_client, monkeypatch):
    monkeypatch.setattr(views, "answer_question", lambda **kwargs: _answer_result(kwargs["question"]))

    response = api_client.post(ASK_URL, {"question": "How much leave?"}, format="json")

    assert response.status_code == 200
    assert response.data["answer"] == "20 days. [1]"
    assert response.data["retrieval"]["mode"] in ("dense", "bm25", "hybrid")
    assert "debug" not in response.data


def test_debug_flag_adds_every_stage(api_client, monkeypatch):
    monkeypatch.setattr(views, "answer_question", lambda **kwargs: _answer_result(kwargs["question"]))

    response = api_client.post(
        ASK_URL, {"question": "How much leave?", "debug": True}, format="json"
    )

    assert set(response.data["debug"]) == {
        "dense_results",
        "bm25_results",
        "fused_results",
        "reranked_results",
        "final_chunks",
        "dropped_citations",
    }


def test_request_options_reach_the_service(api_client, monkeypatch):
    captured: dict = {}

    def fake_answer(**kwargs):
        captured.update(kwargs)
        return _answer_result(kwargs["question"])

    monkeypatch.setattr(views, "answer_question", fake_answer)

    api_client.post(
        ASK_URL,
        {
            "question": "Expense limit?",
            "mode": "bm25",
            "final_k": 7,
            "rerank": False,
            "document_ids": [2],
            "history": [{"role": "user", "content": "What is the expense policy?"}],
        },
        format="json",
    )

    assert captured["config"].mode == "bm25"
    assert captured["config"].final_k == 7
    assert captured["config"].rerank is False
    assert captured["document_ids"] == [2]
    assert captured["history"][0]["content"] == "What is the expense policy?"


def test_provider_failure_is_reported_as_bad_gateway(api_client, monkeypatch):
    def failing_answer(**kwargs):
        raise LLMError("Ollama returned 500: out of memory")

    monkeypatch.setattr(views, "answer_question", failing_answer)

    response = api_client.post(ASK_URL, {"question": "How much leave?"}, format="json")

    assert response.status_code == 502
    assert "out of memory" in response.data["detail"]


def test_invalid_mode_is_rejected(api_client):
    response = api_client.post(
        ASK_URL, {"question": "How much leave?", "mode": "magic"}, format="json"
    )

    assert response.status_code == 400


def test_question_is_required(api_client):
    assert api_client.post(ASK_URL, {}, format="json").status_code == 400


def test_an_unknown_history_role_is_rejected(api_client):
    response = api_client.post(
        ASK_URL,
        {"question": "How much leave?", "history": [{"role": "system", "content": "hi"}]},
        format="json",
    )

    assert response.status_code == 400
