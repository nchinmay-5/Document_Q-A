"""Streamlit front end: sign in, then one of three screens.

Run with:  streamlit run ui/app.py
"""
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from api_client import ApiError, RagApiClient
from screens import debug_screen, documents_screen, qa_screen

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
API_URL = os.environ.get("RAG_API_URL", "http://localhost:8000")

SCREENS = {
    "Documents": documents_screen.render,
    "Q&A": qa_screen.render,
    "Evaluation / Debug": debug_screen.render,
}


def _authenticate(client: RagApiClient) -> None:
    """Sidebar sign-in; the token lives in session state."""
    st.sidebar.header("Sign in")
    action = st.sidebar.radio("Action", ["Login", "Register"], horizontal=True)
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button(action, width="stretch"):
        try:
            token = (
                client.login(username, password)
                if action == "Login"
                else client.register(username, password)
            )
            st.session_state["token"] = token
            st.session_state["username"] = username
            st.rerun()
        except ApiError as exc:
            st.sidebar.error(str(exc))


def main() -> None:
    st.set_page_config(page_title="RAG Document Analytics", layout="wide")
    st.title("RAG Document Analytics")

    client = RagApiClient(API_URL, token=st.session_state.get("token"))

    if not client.token:
        _authenticate(client)
        st.info("Sign in from the sidebar to upload documents and ask questions.")
        return

    st.sidebar.success(f"Signed in as {st.session_state.get('username', 'user')}")
    if st.sidebar.button("Sign out", width="stretch"):
        st.session_state.clear()
        st.rerun()

    screen = st.sidebar.radio("Screen", list(SCREENS))
    SCREENS[screen](client)


main()
