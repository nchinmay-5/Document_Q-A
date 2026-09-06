"""Document parsing: one entry point, one representation.

`parse_document(path)` is the only thing callers use — nothing outside this
module branches on file format. PDF and TXT get heuristic heading detection;
DOCX uses real Word heading styles, which are more reliable.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import docx as python_docx
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Data contracts every parser produces
# ---------------------------------------------------------------------------


@dataclass
class Page:
    """One page of a parsed document, with any headings found on it."""

    page_number: int
    text: str
    headings: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Format-agnostic representation returned by every parser."""

    pages: list[Page]

    @property
    def page_count(self) -> int:
        return len(self.pages)


class UnsupportedDocumentError(ValueError):
    """Raised for a file extension no parser handles."""


# ---------------------------------------------------------------------------
# Heading heuristics, for formats that carry no style information
# ---------------------------------------------------------------------------

MAX_HEADING_WORDS = 12
MAX_HEADING_CHARS = 90

_NUMBERED_PREFIX = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")
_SENTENCE_END = (".", ",", ";", "!", "?")


def looks_like_heading(line: str) -> bool:
    """True for short, title-like lines that do not read as prose."""
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_CHARS:
        return False
    if len(stripped.split()) > MAX_HEADING_WORDS:
        return False
    if stripped.endswith(_SENTENCE_END):
        return False

    is_numbered = bool(_NUMBERED_PREFIX.match(stripped))
    is_upper = stripped.isupper()
    is_title_case = stripped[0].isupper() and not stripped.endswith(",")
    return is_numbered or is_upper or is_title_case


def detect_headings(text: str) -> list[str]:
    """Headings found in `text`, in document order and without duplicates."""
    seen: set[str] = set()
    headings: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and candidate not in seen and looks_like_heading(candidate):
            seen.add(candidate)
            headings.append(candidate)
    return headings


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

TXT_PAGE_BREAK = "\f"


def _parse_pdf(path: Path) -> list[Page]:
    """One Page per physical PDF page."""
    reader = PdfReader(str(path))
    pages: list[Page] = []
    for page_number, pdf_page in enumerate(reader.pages, start=1):
        text = pdf_page.extract_text() or ""
        pages.append(Page(page_number=page_number, text=text, headings=detect_headings(text)))
    return pages


def _parse_docx(path: Path) -> list[Page]:
    """A single Page: DOCX has no page concept until it is rendered."""
    document = python_docx.Document(str(path))

    lines: list[str] = []
    headings: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = (paragraph.style.name or "").lower()
        if (style_name.startswith("heading") or style_name == "title") and text not in headings:
            headings.append(text)
        lines.append(text)

    # Blank-line separation keeps paragraph boundaries for the chunker.
    return [Page(page_number=1, text="\n\n".join(lines), headings=headings)]


def _parse_txt(path: Path) -> list[Page]:
    """Form feeds, when present, mark page breaks."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    return [
        Page(page_number=number, text=text, headings=detect_headings(text))
        for number, text in enumerate(raw.split(TXT_PAGE_BREAK), start=1)
    ]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_PARSERS = {
    "pdf": _parse_pdf,
    "docx": _parse_docx,
    "txt": _parse_txt,
}


def parse_document(path: str | Path) -> ParsedDocument:
    """Parse a file into the common ParsedDocument representation."""
    file_path = Path(path)
    extension = file_path.suffix.lower().lstrip(".")

    parser = _PARSERS.get(extension)
    if parser is None:
        supported = ", ".join(sorted(_PARSERS))
        raise UnsupportedDocumentError(f"Cannot parse '.{extension}'. Supported: {supported}.")

    return ParsedDocument(pages=parser(file_path))
