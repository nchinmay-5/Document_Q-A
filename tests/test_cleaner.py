from ingestion.cleaner import clean_document, clean_text
from ingestion.parser import Page, ParsedDocument


def test_removes_control_characters():
    assert clean_text("Leave\x00 policy\x07") == "Leave policy"


def test_rejoins_hyphenated_line_break():
    assert clean_text("reim-\nbursement is allowed.") == "reimbursement is allowed."


def test_rejoins_wrapped_sentence_but_keeps_paragraphs():
    text = "Employees receive 20 days of\nannual leave.\n\nEligibility\nApplies after 90 days."
    cleaned = clean_text(text)

    assert "20 days of annual leave." in cleaned
    assert "\n\nEligibility" in cleaned


def test_collapses_repeated_whitespace():
    assert clean_text("a    b\n\n\n\nc") == "a b\n\nc"


def test_clean_document_drops_empty_pages():
    parsed = ParsedDocument(
        pages=[
            Page(page_number=1, text="Real content."),
            Page(page_number=2, text="   \x00 \n\n "),
            Page(page_number=3, text="More content."),
        ]
    )

    cleaned = clean_document(parsed)

    assert [page.page_number for page in cleaned.pages] == [1, 3]
    assert cleaned.page_count == 2
