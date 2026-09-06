from ingestion.chunker import DEFAULT_SECTION, chunk_document
from ingestion.parser import Page, ParsedDocument

PAGE_TEXT = (
    "Annual Leave\n"
    "Full-time employees receive 20 days of paid annual leave each calendar year.\n\n"
    "Eligibility\n"
    "Employees become eligible after 90 days of continuous service."
)


def _parsed_page(text: str = PAGE_TEXT, headings: list[str] | None = None) -> ParsedDocument:
    return ParsedDocument(
        pages=[Page(page_number=7, text=text, headings=headings or ["Annual Leave", "Eligibility"])]
    )


def test_chunks_carry_full_metadata():
    chunks = chunk_document(_parsed_page(), document_id=12, user_id=3)

    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"doc12_chunk{index}"
        assert chunk.chunk_index == index
        assert chunk.document_id == 12
        assert chunk.user_id == 3
        assert chunk.page == 7


def test_sections_come_from_headings():
    chunks = chunk_document(_parsed_page(), document_id=1, user_id=1, chunk_size=200, chunk_overlap=20)
    sections = {chunk.section for chunk in chunks}

    assert sections == {"Annual Leave", "Eligibility"}


def test_pages_without_headings_use_default_section():
    parsed = ParsedDocument(pages=[Page(page_number=1, text="Body text only.", headings=[])])

    chunks = chunk_document(parsed, document_id=5, user_id=1)

    assert [chunk.section for chunk in chunks] == [DEFAULT_SECTION]


def test_long_section_is_split_into_several_chunks():
    long_text = "Leave Policy\n" + ("Employees accrue leave monthly. " * 60)
    parsed = ParsedDocument(
        pages=[Page(page_number=1, text=long_text, headings=["Leave Policy"])]
    )

    chunks = chunk_document(parsed, document_id=2, user_id=1, chunk_size=300, chunk_overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 300 for chunk in chunks)
    assert all(chunk.section == "Leave Policy" for chunk in chunks)
