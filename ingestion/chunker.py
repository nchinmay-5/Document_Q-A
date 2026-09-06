"""Structure-aware recursive chunking.

Pages are first split at their headings so a chunk rarely straddles two
sections, then each section is split recursively to the configured size. The
heading a chunk came from is kept as its `section`, which retrieval filters and
citations both use.
"""
from dataclasses import dataclass

from django.conf import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.parser import Page, ParsedDocument

DEFAULT_SECTION = "Body"


@dataclass
class Chunk:
    """An indexable unit of text plus the metadata retrieval filters on."""

    chunk_id: str
    document_id: int
    user_id: int
    chunk_index: int
    page: int
    section: str
    text: str


def _build_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    # Separators run coarse to fine: paragraph, line, sentence, word.
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=False,
    )


def _split_page_into_sections(page: Page) -> list[tuple[str, str]]:
    """Split a page's text at its headings into (section, text) pairs."""
    positions: list[tuple[int, str]] = []
    for heading in page.headings:
        index = page.text.find(heading)
        if index != -1:
            positions.append((index, heading))
    positions.sort()

    if not positions:
        return [(DEFAULT_SECTION, page.text)]

    sections: list[tuple[str, str]] = []
    # Text before the first heading belongs to no section.
    if positions[0][0] > 0:
        sections.append((DEFAULT_SECTION, page.text[: positions[0][0]]))

    for order, (start, heading) in enumerate(positions):
        end = positions[order + 1][0] if order + 1 < len(positions) else len(page.text)
        sections.append((heading, page.text[start:end]))

    return [(section, text) for section, text in sections if text.strip()]


def chunk_document(
    parsed: ParsedDocument,
    *,
    document_id: int,
    user_id: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Turn a parsed document into indexable chunks carrying full metadata."""
    splitter = _build_splitter(
        chunk_size or settings.CHUNK_SIZE_CHARS,
        chunk_overlap or settings.CHUNK_OVERLAP_CHARS,
    )

    chunks: list[Chunk] = []
    for page in parsed.pages:
        for section, section_text in _split_page_into_sections(page):
            for piece in splitter.split_text(section_text):
                text = piece.strip()
                if not text:
                    continue
                index = len(chunks)
                chunks.append(
                    Chunk(
                        chunk_id=f"doc{document_id}_chunk{index}",
                        document_id=document_id,
                        user_id=user_id,
                        chunk_index=index,
                        page=page.page_number,
                        section=section,
                        text=text,
                    )
                )
    return chunks
