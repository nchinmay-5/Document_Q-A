"""Ask-request validation and answer rendering.

Input uses a DRF serializer; output is assembled from the dataclasses'
`describe()` methods, which keeps one obvious place per shape.
"""
from rest_framework import serializers

from qa.service import AnswerResult
from retrieval.retriever import MODES

HISTORY_ROLES = ("user", "assistant")


class HistoryTurnSerializer(serializers.Serializer):
    """One prior turn, used only to resolve follow-up questions."""

    role = serializers.ChoiceField(choices=HISTORY_ROLES)
    content = serializers.CharField(max_length=4000)


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=3, max_length=1000)
    mode = serializers.ChoiceField(choices=MODES, required=False)
    final_k = serializers.IntegerField(min_value=1, max_value=100, required=False)
    rerank = serializers.BooleanField(required=False, default=None, allow_null=True)
    rerank_k = serializers.IntegerField(min_value=1, max_value=50, required=False)
    history = HistoryTurnSerializer(many=True, required=False)
    document_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    content_types = serializers.ListField(child=serializers.CharField(), required=False)
    created_after = serializers.DateTimeField(required=False)
    debug = serializers.BooleanField(required=False, default=False)


def serialize_answer(result: AnswerResult, *, include_debug: bool = False) -> dict:
    """Render an AnswerResult as the API response body."""
    payload = {
        "question": result.question,
        "answer": result.answer,
        "provider": result.provider,
        "query": result.query.describe(),
        "sources": [source.describe() for source in result.sources],
        "citations": [citation.describe() for citation in result.citations],
        "filters": result.filters.describe(),
        "retrieval": result.retrieval.config.describe(),
        "timings_ms": result.timings_ms,
    }

    if include_debug:
        # Per-stage results power the evaluation/debug screen.
        payload["debug"] = {
            "dense_results": [chunk.describe() for chunk in result.retrieval.dense_results],
            "bm25_results": [chunk.describe() for chunk in result.retrieval.bm25_results],
            "fused_results": [chunk.describe() for chunk in result.retrieval.fused_results],
            "reranked_results": [chunk.describe() for chunk in result.retrieval.reranked_results],
            "final_chunks": [chunk.describe() for chunk in result.retrieval.chunks],
            "dropped_citations": result.dropped_citations,
        }

    return payload
