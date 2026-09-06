"""Screen 2 — ask a question, read the answer, its citations and its sources.

Turns are kept in session state so a follow-up question ("what about theirs?")
can be sent to the backend as history and rewritten into a standalone query.
"""
import streamlit as st

from api_client import ApiError, RagApiClient

MODES = ["hybrid", "dense", "bm25"]
HISTORY_KEY = "qa_history"


def _render_citations(citations: list[dict]) -> None:
    """The footnote list the [n] markers in the answer point at."""
    st.markdown("**Citations**")
    for citation in citations:
        section = f" · {citation['section']}" if citation["section"] else ""
        st.markdown(f"[{citation['number']}] {citation['label']}{section}")


def _render_sources(sources: list[dict]) -> None:
    st.subheader("Sources")
    for source in sources:
        label = f"[{source['number']}] {source['filename']} — page {source['page']}"
        with st.expander(label):
            st.caption(f"Section: {source['section'] or '-'} · score {source['score']:.4f}")
            st.write(source["text"])


def _render_conversation(history: list[dict]) -> None:
    for turn in history:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])


def render(client: RagApiClient) -> None:
    st.header("Ask a question")
    history = st.session_state.setdefault(HISTORY_KEY, [])

    controls, reset = st.columns([3, 1])
    mode = controls.selectbox("Retrieval mode", MODES)
    rerank = controls.checkbox("Cross-encoder reranking", value=True)
    if reset.button("Clear conversation", width="stretch"):
        st.session_state[HISTORY_KEY] = []
        st.rerun()

    _render_conversation(history)

    question = st.chat_input("Ask about your documents")
    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    with st.spinner("Retrieving and generating..."):
        try:
            response = client.ask(question, mode=mode, rerank=rerank, history=history)
        except ApiError as exc:
            st.error(str(exc))
            return

    with st.chat_message("assistant"):
        st.write(response["answer"])
        query = response["query"]
        if query["rewritten_by_llm"]:
            st.caption(f"Searched for: {query['rewritten_query']}")
        st.caption(
            f"provider: {response['provider']} · mode: {response['retrieval']['label']} · "
            f"total: {response['timings_ms'].get('total_ms', 0)} ms"
        )

        if response["citations"]:
            _render_citations(response["citations"])
        elif not response["sources"]:
            st.info("No matching evidence was found in your documents.")

    if response["sources"]:
        _render_sources(response["sources"])

    history.extend(
        [{"role": "user", "content": question}, {"role": "assistant", "content": response["answer"]}]
    )
