"""Screen 1 — upload documents, watch ingestion status, delete."""
import pandas as pd
import streamlit as st

from api_client import ApiError, RagApiClient

TABLE_COLUMNS = ["id", "filename", "status", "page_count", "chunk_count", "created_at"]


def _upload_form(client: RagApiClient) -> None:
    uploaded = st.file_uploader("Upload a document", type=["pdf", "docx", "txt"])
    if uploaded and st.button("Ingest document"):
        try:
            document = client.upload_document(uploaded.name, uploaded.getvalue())
            st.success(f"Queued {document['filename']} (id {document['id']}).")
        except ApiError as exc:
            st.error(str(exc))


def _document_table(documents: list[dict]) -> None:
    frame = pd.DataFrame(documents)[TABLE_COLUMNS]
    st.dataframe(frame, width="stretch", hide_index=True)

    failures = [doc for doc in documents if doc["status"] == "FAILED"]
    for failure in failures:
        st.warning(f"{failure['filename']}: {failure['error_message']}")


def render(client: RagApiClient) -> None:
    st.header("Documents")
    _upload_form(client)

    if st.button("Refresh status"):
        st.rerun()

    try:
        documents = client.list_documents()
    except ApiError as exc:
        st.error(str(exc))
        return

    if not documents:
        st.info("No documents yet.")
        return

    _document_table(documents)

    # Deletion also removes the document's chunks from the search index.
    labels = {f"{doc['id']} — {doc['filename']}": doc["id"] for doc in documents}
    selection = st.selectbox("Delete a document", ["-", *labels])
    if selection != "-" and st.button("Delete", type="primary"):
        try:
            client.delete_document(labels[selection])
            st.success("Deleted.")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))
