"""Screen 3 — inspect every retrieval stage for one query.

Shows the rewritten query, what dense, BM25, RRF and the reranker each
returned, the citations that survived validation, and per-stage latency. This
is where the retrieval architecture becomes visible.
"""
import pandas as pd
import streamlit as st

from api_client import ApiError, RagApiClient

STAGE_LABELS = {
    "dense_results": "Dense results",
    "bm25_results": "BM25 results",
    "fused_results": "RRF results",
    "reranked_results": "Cross-encoder results",
    "final_chunks": "Final chunks sent to the LLM",
}


def _stage_table(chunks: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rank": rank,
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "section": chunk["section"],
                "score": round(chunk["score"], 5),
                "preview": chunk["text"][:120].replace("\n", " "),
            }
            for rank, chunk in enumerate(chunks, start=1)
        ]
    )


def _render_query(query: dict) -> None:
    st.subheader("Query")
    st.dataframe(
        pd.DataFrame([
            {"stage": "original", "query": query["original_query"]},
            {"stage": "rewritten", "query": query["rewritten_query"]},
        ]),
        width="stretch",
        hide_index=True,
    )
    st.caption(f"rewriting: {query['reason']}")


def _render_citations(response: dict) -> None:
    st.subheader("Citations")
    citations = response["citations"]
    if citations:
        st.dataframe(pd.DataFrame(citations), width="stretch", hide_index=True)
    else:
        st.caption("The answer carried no valid citation markers.")

    dropped = response.get("debug", {}).get("dropped_citations", [])
    if dropped:
        st.warning(f"Markers dropped as unsupported by the evidence: {dropped}")


def render(client: RagApiClient) -> None:
    st.header("Evaluation / Debug")
    question = st.text_input("Query to inspect", placeholder="expense claim deadline")
    history_text = st.text_area(
        "Conversation history (optional, one 'role: text' per line)",
        placeholder="user: How much annual leave do employees get?\nassistant: 20 days. [1]",
    )
    rerank = st.checkbox("Cross-encoder reranking", value=True)

    if not (question and st.button("Run pipeline")):
        return

    history = _parse_history(history_text)
    with st.spinner("Running retrieval pipeline..."):
        try:
            response = client.ask(
                question, mode="hybrid", debug=True, rerank=rerank, history=history
            )
        except ApiError as exc:
            st.error(str(exc))
            return

    _render_query(response["query"])

    st.subheader("Latency (ms)")
    st.dataframe(pd.DataFrame([response["timings_ms"]]), width="stretch", hide_index=True)

    st.subheader("Configuration")
    st.json({"retrieval": response["retrieval"], "filters": response["filters"]})

    st.subheader("Answer")
    st.write(response["answer"])
    _render_citations(response)

    for key, label in STAGE_LABELS.items():
        chunks = response.get("debug", {}).get(key, [])
        st.subheader(f"{label} ({len(chunks)})")
        if chunks:
            st.dataframe(_stage_table(chunks), width="stretch", hide_index=True)
        else:
            st.caption("No results for this stage.")


def _parse_history(text: str) -> list[dict]:
    """Read the free-text history box into the turns the API expects."""
    turns = []
    for line in text.splitlines():
        role, separator, content = line.partition(":")
        if separator and role.strip().lower() in ("user", "assistant") and content.strip():
            turns.append({"role": role.strip().lower(), "content": content.strip()})
    return turns
