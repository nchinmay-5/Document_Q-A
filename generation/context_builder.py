"""Builds the evidence block sent to the LLM, plus the source map behind it.

The source map is what turns a model's "[2]" into a real document, page and
section, so it is produced here rather than parsed out of the answer later.
"""
from dataclasses import dataclass

from django.conf import settings

from retrieval.types import RetrievedChunk

SOURCE_TEMPLATE = """SOURCE {number}
Document: {filename}
Page: {page}
Section: {section}

{text}"""


@dataclass(frozen=True)
class Source:
    """One numbered piece of evidence shown to the model."""

    number: int
    chunk_id: str
    document_id: int
    filename: str
    page: int
    section: str
    text: str
    score: float

    def describe(self) -> dict:
        return {
            "number": self.number,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "page": self.page,
            "section": self.section,
            "score": self.score,
            "text": self.text,
        }


@dataclass
class BuiltContext:
    text: str
    sources: list[Source]


def build_context(
    chunks: list[RetrievedChunk],
    *,
    filenames: dict[int, str],
    max_sources: int | None = None,
    char_budget: int | None = None,
) -> BuiltContext:
    """Render the top chunks as numbered SOURCE blocks within a char budget."""
    max_sources = max_sources or settings.RETRIEVAL_CONTEXT_K
    char_budget = char_budget or settings.CONTEXT_CHAR_BUDGET

    sources: list[Source] = []
    blocks: list[str] = []
    used_chars = 0

    for chunk in chunks[:max_sources]:
        source = Source(
            number=len(sources) + 1,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=filenames.get(chunk.document_id, f"document {chunk.document_id}"),
            page=chunk.page,
            section=chunk.section,
            text=chunk.text,
            score=chunk.score,
        )
        block = SOURCE_TEMPLATE.format(
            number=source.number,
            filename=source.filename,
            page=source.page,
            section=source.section or "-",
            text=source.text,
        )
        # Stop before exceeding the budget rather than truncating evidence.
        if used_chars + len(block) > char_budget and sources:
            break

        sources.append(source)
        blocks.append(block)
        used_chars += len(block)

    return BuiltContext(text="\n\n---\n\n".join(blocks), sources=sources)
