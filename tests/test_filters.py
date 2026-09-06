from datetime import datetime, timezone

import pytest

from retrieval.filters import SearchFilters


def test_user_filter_is_always_applied():
    clauses = SearchFilters(user_id=42).to_es_filters()

    assert clauses == [{"term": {"user_id": 42}}]


def test_user_id_is_required():
    with pytest.raises(TypeError):
        SearchFilters()  # type: ignore[call-arg]


def test_optional_filters_are_added_when_given():
    filters = SearchFilters(
        user_id=1,
        document_ids=[3, 4],
        content_types=["pdf"],
        created_after=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    clauses = filters.to_es_filters()

    assert {"term": {"user_id": 1}} in clauses
    assert {"terms": {"document_id": [3, 4]}} in clauses
    assert {"terms": {"content_type": ["pdf"]}} in clauses
    assert clauses[-1]["range"]["created_at"]["gte"].startswith("2026-01-01")


def test_empty_optional_filters_are_skipped():
    clauses = SearchFilters(user_id=1, document_ids=[], content_types=[]).to_es_filters()

    assert len(clauses) == 1


def test_describe_is_serialisable():
    described = SearchFilters(user_id=9, document_ids=[1]).describe()

    assert described == {
        "user_id": 9,
        "document_ids": [1],
        "content_types": None,
        "created_after": None,
    }
