"""Practical text clean-up applied to parsed pages before chunking.

Deliberately mechanical: no language detection, no NLP. It fixes the artefacts
PDF extraction actually produces.
"""
import re

from ingestion.parser import Page, ParsedDocument

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_REPEATED_SPACES = re.compile(r"[ \t]{2,}")
_REPEATED_NEWLINES = re.compile(r"\n{3,}")

_LINE_END_PUNCTUATION = (".", ":", ";", "!", "?", "•", "-")


def _join_wrapped_lines(text: str) -> str:
    """Rejoin lines a PDF extractor split mid-sentence, keeping paragraphs."""
    output: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        continues_previous = (
            output
            and output[-1]
            and stripped
            and not output[-1].endswith(_LINE_END_PUNCTUATION)
            and stripped[0].islower()
        )
        if continues_previous:
            output[-1] = f"{output[-1]} {stripped}"
        else:
            output.append(stripped)
    return "\n".join(output)


def clean_text(text: str) -> str:
    """Normalise whitespace, control characters and broken lines."""
    text = _CONTROL_CHARS.sub("", text)
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = _join_wrapped_lines(text)
    text = _REPEATED_SPACES.sub(" ", text)
    text = _REPEATED_NEWLINES.sub("\n\n", text)
    return text.strip()


def clean_document(parsed: ParsedDocument) -> ParsedDocument:
    """Clean every page and drop the ones left with no content."""
    pages = [
        Page(page_number=page.page_number, text=cleaned, headings=page.headings)
        for page in parsed.pages
        if (cleaned := clean_text(page.text))
    ]
    return ParsedDocument(pages=pages)
