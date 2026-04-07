"""PolicyLens Streamlit entry point."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

DEFAULT_SESSION_STATE: dict[str, Any] = {
    "uploaded_docs": [],
    "extracted_results": [],
    "active_doc_index": 0,
    "chat_history": {},
    "processing_status": {},
}


def init_session_state() -> None:
    """Initialise all shared session state keys with default values."""
    for key, value in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            if isinstance(value, dict):
                st.session_state[key] = dict(value)
            elif isinstance(value, list):
                st.session_state[key] = list(value)
            else:
                st.session_state[key] = value


def _clear_all_data() -> None:
    """Reset all shared session keys to defaults."""
    for key, value in DEFAULT_SESSION_STATE.items():
        if isinstance(value, dict):
            st.session_state[key] = dict(value)
        elif isinstance(value, list):
            st.session_state[key] = list(value)
        else:
            st.session_state[key] = value


def _risk_summary() -> tuple[int, int]:
    """Calculate total high and medium risk flags from extracted results.

    Returns:
        Tuple containing (high_count, medium_count).
    """
    results = st.session_state.get("extracted_results", [])
    high_count = 0
    medium_count = 0
    for result in results:
        for flag in result.get("flags", []):
            severity = str(flag.get("severity", ""))
            if severity == "High":
                high_count += 1
            elif severity == "Medium":
                medium_count += 1
    return high_count, medium_count


def render_sidebar() -> None:
    """Render sidebar content and navigation links."""
    doc_count: int = len(st.session_state.get("extracted_results", []))
    high_count, medium_count = _risk_summary()
    with st.sidebar:
        st.title("PolicyLens")
        st.caption("Insurance Document Intelligence")
        st.write(f"**Documents Analysed:** {doc_count}")
        if doc_count > 0:
            st.write(f"**Risk Snapshot:** {high_count} High, {medium_count} Medium")
        st.divider()
        st.subheader("Navigation")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_Upload.py", label="Upload", icon="📄")
        st.page_link("pages/2_Results.py", label="Results", icon="📊")
        st.page_link("pages/3_Chat.py", label="Chat", icon="💬")
        st.page_link("pages/4_Export.py", label="Export", icon="⬇️")
        st.divider()
        if st.button("Clear All Data", use_container_width=True):
            _clear_all_data()
            st.success("Session data cleared.")
            st.rerun()


def render_homepage() -> None:
    """Render homepage content and getting-started action."""
    st.title("🛡️ PolicyLens")
    st.subheader("Insurance Document Intelligence for extraction, risk, and Q&A.")
    st.write(
        "Process real-world insurance PDFs with hybrid NLP + LLM extraction, detect risk signals, "
        "and explore content through document-grounded chat."
    )

    feature_col_1, feature_col_2, feature_col_3 = st.columns(3)
    with feature_col_1:
        st.markdown("### 🔍 Smart Extraction")
        st.write("Hybrid spaCy + Claude extraction for structured policy intelligence.")
    with feature_col_2:
        st.markdown("### 🚨 Risk Flags")
        st.write("Automated rule checks for expiry, limits, deductibles, and missing fields.")
    with feature_col_3:
        st.markdown("### 💬 Document Chat")
        st.write("Ask contextual questions and get grounded answers from policy text.")

    st.markdown("### Supported Document Types")
    st.markdown(
        "- Policy Document\n"
        "- Certificate of Insurance\n"
        "- Endorsement\n"
        "- Claims Document"
    )

    doc_count: int = len(st.session_state.get("extracted_results", []))
    high_count, medium_count = _risk_summary()
    if doc_count > 0:
        st.info(
            f"{doc_count} documents analysed, {high_count + medium_count} priority flags detected."
        )

    st.page_link("pages/1_Upload.py", label="Get Started", icon="🚀")


def main() -> None:
    """Run the Streamlit app entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    st.set_page_config(page_title="PolicyLens", page_icon="🛡️", layout="wide")
    init_session_state()
    render_sidebar()
    render_homepage()


if __name__ == "__main__":
    main()
