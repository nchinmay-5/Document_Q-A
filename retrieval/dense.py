"""Dense retrieval: approximate kNN over chunk embeddings."""
from ingestion.embeddings import get_embedding_backend
from retrieval.filters import SearchFilters
from retrieval.index import SOURCE_FIELDS, chunk_index_name, get_client
from retrieval.types import RetrievedChunk

RETRIEVER_NAME = "dense"
CANDIDATE_MULTIPLIER = 4  # HNSW candidates to scan per requested hit

def search(query: str, *, filters: SearchFilters, top_k: int) -> list[RetrievedChunk]:
    """Top-k semantically similar chunks, restricted by metadata filters."""
    query_vector = get_embedding_backend().embed_query(query)

    response = get_client().search(
        index=chunk_index_name(),
        knn={
            "field": "embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": max(top_k * CANDIDATE_MULTIPLIER, 50),
            "filter": filters.to_es_filters(),
        },
        size=top_k,
        source=SOURCE_FIELDS,
    )

    return [RetrievedChunk.from_hit(hit, RETRIEVER_NAME) for hit in response["hits"]["hits"]]
