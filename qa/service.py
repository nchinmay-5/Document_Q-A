"""Question answering, one stage at a time.

rewrite -> filter -> retrieve -> fuse -> rerank -> build context -> generate
        -> resolve citations

Search filters are built here from the authenticated user, so no caller can ask
a question that reaches another user's documents.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime

from django.contrib.auth.models import User

from documents.models import Document
from generation.citations import Citation, resolve_citations
from generation.context_builder import Source, build_context
from generation.llm import get_llm_client
from generation.prompts import NO_EVIDENCE_ANSWER, SYSTEM_PROMPT, build_answer_prompt
from generation.query_rewriter import RewrittenQuery, rewrite_query
from retrieval.filters import SearchFilters
from retrieval.retriever import RetrievalConfig, RetrievalResult, retrieve


@dataclass
class AnswerResult:
    question: str
    answer: str
    provider: str
    query: RewrittenQuery
    sources: list[Source]
    citations: list[Citation]
    filters: SearchFilters
    retrieval: RetrievalResult
    dropped_citations: list[int] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


def _document_filenames(user: User, document_ids: list[int]) -> dict[int, str]:
    """Map document id to filename for the retrieved chunks (one query)."""
    rows = Document.objects.filter(user=user, id__in=document_ids).values_list("id", "filename")
    return dict(rows)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def answer_question(
    *,
    user: User,
    question: str,
    config: RetrievalConfig | None = None,
    history: list[dict] | None = None,
    document_ids: list[int] | None = None,
    content_types: list[str] | None = None,
    created_after: datetime | None = None,
) -> AnswerResult:
    """Answer a question over the user's own indexed documents."""
    filters = SearchFilters(
        user_id=user.id,
        document_ids=document_ids,
        content_types=content_types,
        created_after=created_after,
    )

    started = time.perf_counter()
    query = rewrite_query(question, history)
    timings = {"rewrite_ms": _elapsed_ms(started)}

    # Retrieval runs on the standalone query; the user still sees their own.
    retrieval = retrieve(query.rewritten, filters=filters, config=config)
    timings.update(retrieval.timings_ms)

    filenames = _document_filenames(user, [chunk.document_id for chunk in retrieval.chunks])
    context = build_context(retrieval.chunks, filenames=filenames)

    client = get_llm_client()

    # No evidence means no LLM call: the honest answer is deterministic.
    if not context.sources:
        timings["generation_ms"] = 0.0
        timings["total_ms"] = round(timings["rewrite_ms"] + timings.get("retrieval_ms", 0.0), 2)
        return AnswerResult(
            question=question,
            answer=NO_EVIDENCE_ANSWER,
            provider=client.name,
            query=query,
            sources=[],
            citations=[],
            filters=filters,
            retrieval=retrieval,
            timings_ms=timings,
        )

    started = time.perf_counter()
    raw_answer = client.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_answer_prompt(question, context.text),
    )
    timings["generation_ms"] = _elapsed_ms(started)

    cited = resolve_citations(raw_answer, context.sources)
    timings["total_ms"] = round(
        timings["rewrite_ms"] + timings.get("retrieval_ms", 0.0) + timings["generation_ms"], 2
    )

    return AnswerResult(
        question=question,
        answer=cited.answer,
        provider=client.name,
        query=query,
        sources=context.sources,
        citations=cited.citations,
        filters=filters,
        retrieval=retrieval,
        dropped_citations=cited.dropped_numbers,
        timings_ms=timings,
    )
