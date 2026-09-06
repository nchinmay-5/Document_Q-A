"""Lexical retrieval: Elasticsearch BM25 over chunk text.

Same signature as retrieval.dense.search, so fusion, evaluation and the UI stay
retriever-agnostic.
"""
from retrieval.filters import SearchFilters
from retrieval.index import SOURCE_FIELDS, chunk_index_name, get_client
from retrieval.types import RetrievedChunk

RETRIEVER_NAME = "bm25"
SECTION_BOOST = 1.5


def search(query: str, *, filters: SearchFilters, top_k: int) -> list[RetrievedChunk]:
    """Top-k keyword matches, restricted by metadata filters."""
    response = get_client().search(
        index=chunk_index_name(),
        query={
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["text", f"section^{SECTION_BOOST}"],
                        }
                    }
                ],
                "filter": filters.to_es_filters(),
            }
        },
        size=top_k,
        source=SOURCE_FIELDS,
    )

    return [RetrievedChunk.from_hit(hit, RETRIEVER_NAME) for hit in response["hits"]["hits"]]
