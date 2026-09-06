import pytest

from ingestion.parser import UnsupportedDocumentError, detect_headings, parse_document
from samples.build_samples import HR_POLICY, SECURITY_POLICY, write_docx, write_pdf, write_txt


def test_txt_form_feed_marks_pages(tmp_path):
    path = tmp_path / "policy.txt"
    path.write_text("Page one text.\fPage two text.", encoding="utf-8")

    parsed = parse_document(path)

    assert parsed.page_count == 2
    assert parsed.pages[1].text.strip() == "Page two text."


def test_pdf_parsed_page_by_page(tmp_path):
    pytest.importorskip("reportlab")
    path = tmp_path / "hr_policy.pdf"
    write_pdf(HR_POLICY, path)

    parsed = parse_document(path)

    assert parsed.page_count == len(HR_POLICY["pages"])
    assert "20 days of paid annual leave" in parsed.pages[0].text
    assert "Annual Leave" in parsed.pages[0].headings


def test_docx_uses_word_heading_styles(tmp_path):
    path = tmp_path / "security_policy.docx"
    write_docx(SECURITY_POLICY, path)

    parsed = parse_document(path)

    assert parsed.page_count == 1
    assert "Password Requirements" in parsed.pages[0].headings
    assert "14 characters" in parsed.pages[0].text


def test_txt_sample_headings_are_detected(tmp_path):
    path = tmp_path / "finance.txt"
    write_txt(SECURITY_POLICY, path)

    parsed = parse_document(path)

    assert "Incident Reporting" in parsed.pages[0].headings


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# hello", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentError):
        parse_document(path)


def test_prose_lines_are_not_headings():
    text = "Leave Policy\nEmployees receive 20 days of paid annual leave each year."

    assert detect_headings(text) == ["Leave Policy"]
