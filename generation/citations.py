"""Maps the [n] markers in an answer back to real documents.

Nothing here asks the model where a fact came from — the context builder
already assigned each number to a chunk, so resolution is a lookup. The only
model-dependent step is reading the markers it emitted, and any marker pointing
at a source that was never supplied is dropped rather than shown.
"""
import re
from dataclasses import dataclass

from generation.context_builder import Source

# Matches [1], [2,3] and [2, 3]; a group is expanded into its numbers.
MARKER_PATTERN = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


@dataclass(frozen=True)
class Citation:
    """One source the answer actually referenced."""

    number: int
    chunk_id: str
    document_id: int
    filename: str
    page: int
    section: str

    @classmethod
    def from_source(cls, source: Source) -> "Citation":
        return cls(
            number=source.number,
            chunk_id=source.chunk_id,
            document_id=source.document_id,
            filename=source.filename,
            page=source.page,
            section=source.section,
        )

    @property
    def label(self) -> str:
        """Display form, e.g. "hr_policy.pdf, Page 12"."""
        return f"{self.filename}, Page {self.page}"

    def describe(self) -> dict:
        return {
            "number": self.number,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "page": self.page,
            "section": self.section,
            "label": self.label,
        }


@dataclass
class CitedAnswer:
    """The answer with only verifiable markers left, and what they point to."""

    answer: str
    citations: list[Citation]
    dropped_numbers: list[int]  # markers the model invented

    @property
    def is_grounded(self) -> bool:
        return bool(self.citations)


def _numbers_in(marker_body: str) -> list[int]:
    return [int(part) for part in marker_body.split(",")]


def resolve_citations(answer: str, sources: list[Source]) -> CitedAnswer:
    """Validate the answer's [n] markers against the sources that were supplied."""
    by_number = {source.number: source for source in sources}
    cited: dict[int, Citation] = {}
    dropped: list[int] = []

    def replace(match: re.Match) -> str:
        kept = []
        for number in _numbers_in(match.group(1)):
            source = by_number.get(number)
            if source is None:
                if number not in dropped:
                    dropped.append(number)
                continue
            cited.setdefault(number, Citation.from_source(source))
            kept.append(number)
        # An entirely unusable marker leaves no trace in the answer.
        return "".join(f"[{number}]" for number in kept)

    cleaned = MARKER_PATTERN.sub(replace, answer)
    # Collapse the whitespace a removed marker may have left behind.
    cleaned = re.sub(r" {2,}", " ", cleaned).replace(" .", ".").strip()

    return CitedAnswer(
        answer=cleaned,
        citations=sorted(cited.values(), key=lambda citation: citation.number),
        dropped_numbers=dropped,
    )
