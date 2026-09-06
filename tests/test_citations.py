from generation.citations import resolve_citations
from generation.context_builder import Source


def _source(number: int, filename: str = "hr_policy.pdf", page: int = 12) -> Source:
    return Source(
        number=number,
        chunk_id=f"doc1_chunk{number}",
        document_id=1,
        filename=filename,
        page=page,
        section="Annual Leave",
        text="Employees receive 20 days of annual leave.",
        score=0.9,
    )


def test_markers_resolve_to_document_and_page():
    cited = resolve_citations("Employees receive 20 days. [1]", [_source(1)])

    assert cited.answer == "Employees receive 20 days. [1]"
    assert cited.citations[0].label == "hr_policy.pdf, Page 12"
    assert cited.citations[0].chunk_id == "doc1_chunk1"
    assert cited.is_grounded


def test_only_cited_sources_become_citations():
    cited = resolve_citations("Answer. [2]", [_source(1), _source(2)])

    assert [citation.number for citation in cited.citations] == [2]


def test_a_grouped_marker_is_expanded():
    cited = resolve_citations("Answer. [1, 2]", [_source(1), _source(2)])

    assert [citation.number for citation in cited.citations] == [1, 2]


def test_repeated_markers_are_listed_once():
    cited = resolve_citations("First. [1] Second. [1]", [_source(1)])

    assert len(cited.citations) == 1


def test_invented_markers_are_dropped_from_the_answer():
    cited = resolve_citations("Answer. [7]", [_source(1)])

    assert cited.answer == "Answer."
    assert cited.citations == []
    assert cited.dropped_numbers == [7]
    assert not cited.is_grounded


def test_a_group_keeps_its_valid_numbers_only():
    cited = resolve_citations("Answer. [1, 9]", [_source(1)])

    assert cited.answer == "Answer. [1]"
    assert cited.dropped_numbers == [9]


def test_an_uncited_answer_stays_intact():
    cited = resolve_citations("The provided documents do not contain this information.", [])

    assert cited.answer == "The provided documents do not contain this information."
    assert cited.citations == []
