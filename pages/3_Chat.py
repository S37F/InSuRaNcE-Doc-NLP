"""Chat interface for document Q&A."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.chat_engine import answer_question


def _get_selected_result() -> dict[str, Any] | None:
    """Return currently selected result record.

    Returns:
        Selected result dictionary or None if no results exist.
    """
    results: list[dict[str, Any]] = st.session_state.get("extracted_results", [])
    if not results:
        return None

    filenames = [str(item.get("filename", "unknown.pdf")) for item in results]
    selected_filename = st.selectbox("Select Document", options=filenames, index=0)
    return next((item for item in results if item.get("filename") == selected_filename), None)


def _render_chat_history(filename: str) -> None:
    """Render existing chat messages for selected document.

    Args:
        filename: Active document filename.
    """
    history_map: dict[str, list[dict[str, str]]] = st.session_state["chat_history"]
    history = history_map.get(filename, [])
    for message in history:
        role = message.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(message.get("content", ""))


def _get_document_text(filename: str, selected_result: dict[str, Any]) -> str:
    """Resolve full document text from result or uploaded docs session state.

    Args:
        filename: Active document filename.
        selected_result: Selected extraction result.

    Returns:
        Best-available full text string for chat context.
    """
    text_from_result = str(selected_result.get("full_text", "")).strip()
    if text_from_result:
        return text_from_result

    uploaded_docs: list[dict[str, Any]] = st.session_state.get("uploaded_docs", [])
    uploaded_match = next((doc for doc in uploaded_docs if doc.get("filename") == filename), None)
    if not uploaded_match:
        return ""
    return str(uploaded_match.get("raw_text", ""))


st.title("💬 Chat with Document")
results = st.session_state.get("extracted_results", [])
if not results:
    st.info("No documents processed yet.")
    st.page_link("pages/1_Upload.py", label="Go to Upload Page", icon="📄")
else:
    selected_result = _get_selected_result()
    if not selected_result:
        st.info("Could not load selected document.")
    else:
        filename = str(selected_result.get("filename", "unknown.pdf"))
        doc_type = str(selected_result.get("doc_type", "unknown"))
        full_text = _get_document_text(filename, selected_result)
        st.session_state["chat_history"].setdefault(filename, [])

        with st.sidebar:
            st.subheader("Document Context")
            st.write(f"**Filename:** {filename}")
            st.write(f"**Document Type:** {doc_type.title()}")
            if st.button("Clear Chat"):
                st.session_state["chat_history"][filename] = []
                st.rerun()

        _render_chat_history(filename)

        user_question = st.chat_input("Ask a question about this document...")
        if user_question:
            st.session_state["chat_history"][filename].append(
                {"role": "user", "content": user_question}
            )
            with st.spinner("Thinking..."):
                assistant_reply = answer_question(
                    question=user_question,
                    full_text=full_text,
                    chat_history=st.session_state["chat_history"][filename],
                    doc_type=doc_type,
                )
            st.session_state["chat_history"][filename].append(
                {"role": "assistant", "content": assistant_reply}
            )
            st.rerun()
