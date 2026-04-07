"""Results display page for extracted fields and risk flags."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _style_missing_values(dataframe: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply highlighting style for missing values.

    Args:
        dataframe: Field/value dataframe.

    Returns:
        Styled dataframe object with missing values highlighted.
    """
    def highlight_row(row: pd.Series) -> list[str]:
        value = row.get("Value")
        if value is None:
            return ["", "background-color: #FADBD8; color: #922B21; font-weight: 600;"]
        return ["", ""]

    return dataframe.style.apply(highlight_row, axis=1)


def _render_document_info(selected_result: dict[str, Any]) -> None:
    """Render top-level information for selected document.

    Args:
        selected_result: Processed result record for one document.
    """
    st.subheader("Document Info")
    doc_type: str = str(selected_result.get("doc_type", "unknown"))
    badge_color: str = {
        "policy": "#1B4F72",
        "certificate": "#117A65",
        "endorsement": "#8E44AD",
        "claim": "#B9770E",
        "unknown": "#7B7D7D",
    }.get(doc_type, "#7B7D7D")
    st.markdown(
        f"<span style='background:{badge_color};color:#fff;padding:0.3rem 0.6rem;"
        f"border-radius:0.4rem;font-size:0.85rem;'>{doc_type.title()}</span>",
        unsafe_allow_html=True,
    )
    st.write(f"**Filename:** {selected_result.get('filename', 'unknown.pdf')}")
    st.write(f"**Page Count:** {selected_result.get('page_count', 0)}")


def _render_extracted_fields(selected_result: dict[str, Any]) -> None:
    """Render extracted fields as a two-column dataframe.

    Args:
        selected_result: Processed result record for one document.
    """
    st.subheader("Extracted Fields")
    fields: dict[str, Any] = selected_result.get("fields", {})
    rows: list[dict[str, Any]] = []
    for key, value in fields.items():
        rows.append({"Field": key.replace("_", " ").title(), "Value": value})
    fields_df = pd.DataFrame(rows)
    styled = _style_missing_values(fields_df)
    st.dataframe(styled, use_container_width=True)


def _render_risk_flags(selected_result: dict[str, Any]) -> None:
    """Render risk flag outputs with severity-aware display.

    Args:
        selected_result: Processed result record for one document.
    """
    st.subheader("Risk Flags")
    flags: list[dict[str, str]] = selected_result.get("flags", [])
    if not flags:
        st.success("No risk flags detected ✅")
        return

    high_count = 0
    medium_count = 0
    for flag in flags:
        severity = str(flag.get("severity", "Low"))
        flag_name = str(flag.get("flag_name", "Unnamed Flag"))
        details = str(flag.get("details", ""))
        message = f"**{flag_name}** — {details}"
        if severity == "High":
            high_count += 1
            st.error(message)
        elif severity == "Medium":
            medium_count += 1
            st.warning(message)
        else:
            st.info(message)
    st.caption(f"{high_count} High, {medium_count} Medium flags")


st.title("📊 Results")
results: list[dict[str, Any]] = st.session_state.get("extracted_results", [])
if not results:
    st.info("No documents processed yet.")
    st.page_link("pages/1_Upload.py", label="Go to Upload Page", icon="📄")
else:
    filenames: list[str] = [str(item.get("filename", "unknown.pdf")) for item in results]
    selected_filename = st.selectbox("Select Document", options=filenames, index=0)
    selected_result = next(item for item in results if item.get("filename") == selected_filename)
    _render_document_info(selected_result)
    _render_extracted_fields(selected_result)
    _render_risk_flags(selected_result)

    col_chat, col_export = st.columns(2)
    with col_chat:
        if st.button("Go to Chat →"):
            st.switch_page("pages/3_Chat.py")
    with col_export:
        if st.button("Export →"):
            st.switch_page("pages/4_Export.py")
