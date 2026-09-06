from generation.context_builder import build_context
from retrieval.types import RetrievedChunk


def _chunk(chunk_id: str, document_id: int = 1, page: int = 3, text: str = "Leave is 20 days.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        page=page,
        section="Annual Leave",
        text=text,
        score=0.9,
        retriever="rrf",
    )


def test_sources_are_numbered_and_rendered():
    context = build_context(
        [_chunk("c1"), _chunk("c2", document_id=2, page=8)],
        filenames={1: "hr_policy.pdf", 2: "finance_policy.txt"},
    )

    assert [source.number for source in context.sources] == [1, 2]
    assert "SOURCE 1" in context.text
    assert "Document: hr_policy.pdf" in context.text
    assert "Page: 8" in context.text


def test_source_count_is_capped():
    chunks = [_chunk(f"c{index}") for index in range(10)]

    context = build_context(chunks, filenames={1: "hr_policy.pdf"}, max_sources=3)

    assert len(context.sources) == 3


def test_char_budget_stops_adding_sources_but_keeps_one():
    chunks = [_chunk("c1", text="x" * 500), _chunk("c2", text="y" * 500)]

    context = build_context(chunks, filenames={1: "hr_policy.pdf"}, char_budget=300)

    assert len(context.sources) == 1


def test_unknown_document_id_falls_back_to_a_placeholder():
    context = build_context([_chunk("c1", document_id=99)], filenames={})

    assert context.sources[0].filename == "document 99"


def test_no_chunks_produces_no_sources():
    context = build_context([], filenames={})

    assert context.sources == []
    assert context.text == ""
