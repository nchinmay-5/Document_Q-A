"""Retrieval orchestration.

Keeps the stages explicit — retrieve, fuse, rerank — and reports what each
stage produced so the debug screen (and later, tracing) can show the whole
pipeline.
"""
import time
from dataclasses import dataclass, field

from django.conf import settings

from reranking.reranker import rerank
from retrieval import bm25, dense
from retrieval.filters import SearchFilters
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.types import RetrievedChunk

MODE_DENSE = "dense"
MODE_BM25 = "bm25"
MODE_HYBRID = "hybrid"
MODES = (MODE_DENSE, MODE_BM25, MODE_HYBRID)


@dataclass(frozen=True)
class RetrievalConfig:
    """One retrieval configuration; also the unit of comparison in evaluation."""

    mode: str = MODE_HYBRID
    dense_k: int = 30
    bm25_k: int = 30
    final_k: int = 20
    rrf_k: int = 60
    rerank: bool = False
    rerank_k: int = 5

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"Unknown retrieval mode '{self.mode}'. Supported: {', '.join(MODES)}.")

    @classmethod
    def from_settings(cls, **overrides) -> "RetrievalConfig":
        """Defaults from settings, with any explicitly provided overrides."""
        values = {
            "mode": settings.RETRIEVAL_MODE,
            "dense_k": settings.RETRIEVAL_DENSE_K,
            "bm25_k": settings.RETRIEVAL_BM25_K,
            "final_k": settings.RETRIEVAL_FINAL_K,
            "rrf_k": settings.RRF_K,
            "rerank": settings.RERANK_ENABLED,
            "rerank_k": settings.RERANK_TOP_K,
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)

    @property
    def label(self) -> str:
        """Short name for this configuration, used when comparing runs."""
        return f"{self.mode}+reranker" if self.rerank else self.mode

    def describe(self) -> dict:
        return {
            "label": self.label,
            "mode": self.mode,
            "dense_k": self.dense_k,
            "bm25_k": self.bm25_k,
            "final_k": self.final_k,
            "rrf_k": self.rrf_k,
            "rerank": self.rerank,
            "rerank_k": self.rerank_k,
        }


@dataclass
class RetrievalResult:
    """Final candidates plus every intermediate stage, for inspection."""

    config: RetrievalConfig
    chunks: list[RetrievedChunk]
    dense_results: list[RetrievedChunk] = field(default_factory=list)
    bm25_results: list[RetrievedChunk] = field(default_factory=list)
    fused_results: list[RetrievedChunk] = field(default_factory=list)
    reranked_results: list[RetrievedChunk] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def retrieve(
    query: str,
    *,
    filters: SearchFilters,
    config: RetrievalConfig | None = None,
) -> RetrievalResult:
    """Run the configured retrieval pipeline for one query."""
    config = config or RetrievalConfig.from_settings()
    timings: dict[str, float] = {}
    dense_results: list[RetrievedChunk] = []
    bm25_results: list[RetrievedChunk] = []
    fused_results: list[RetrievedChunk] = []
    reranked_results: list[RetrievedChunk] = []

    if config.mode in (MODE_DENSE, MODE_HYBRID):
        started = time.perf_counter()
        dense_results = dense.search(query, filters=filters, top_k=config.dense_k)
        timings["dense_ms"] = _elapsed_ms(started)

    if config.mode in (MODE_BM25, MODE_HYBRID):
        started = time.perf_counter()
        bm25_results = bm25.search(query, filters=filters, top_k=config.bm25_k)
        timings["bm25_ms"] = _elapsed_ms(started)

    if config.mode == MODE_HYBRID:
        started = time.perf_counter()
        fused_results = reciprocal_rank_fusion(
            [dense_results, bm25_results], k=config.rrf_k, top_k=config.final_k
        )
        timings["fusion_ms"] = _elapsed_ms(started)
        chunks = fused_results
    elif config.mode == MODE_DENSE:
        chunks = dense_results[: config.final_k]
    else:
        chunks = bm25_results[: config.final_k]

    # Reranking is the last ordering stage: it reads the query and each
    # candidate together, which no earlier stage does.
    if config.rerank:
        started = time.perf_counter()
        reranked_results = rerank(query, chunks, top_k=config.rerank_k)
        timings["rerank_ms"] = _elapsed_ms(started)
        chunks = reranked_results

    timings["retrieval_ms"] = round(sum(timings.values()), 2)
    return RetrievalResult(
        config=config,
        chunks=chunks,
        dense_results=dense_results,
        bm25_results=bm25_results,
        fused_results=fused_results,
        reranked_results=reranked_results,
        timings_ms=timings,
    )
