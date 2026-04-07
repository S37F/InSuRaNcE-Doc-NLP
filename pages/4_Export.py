"""Export interface for PolicyLens outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from utils.export import export_to_csv, export_to_excel


def _collect_all_flags(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten risk flags across all result records.

    Args:
        results: Processed results list.

    Returns:
        Flat list of flags.
    """
    all_flags: list[dict[str, Any]] = []
    for result in results:
        result_flags = result.get("flags", [])
        if isinstance(result_flags, list):
            all_flags.extend(result_flags)
    return all_flags


def _summary_table(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Build summary table for export page.

    Args:
        results: Processed results list.

    Returns:
        DataFrame with filename, doc type, and flag count.
    """
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "Filename": result.get("filename"),
                "Doc Type": str(result.get("doc_type", "unknown")).title(),
                "Flag Count": len(result.get("flags", [])),
            }
        )
    return pd.DataFrame(rows)


st.title("⬇️ Export Results")
results: list[dict[str, Any]] = st.session_state.get("extracted_results", [])
if not results:
    st.info("No documents processed yet.")
    st.page_link("pages/1_Upload.py", label="Go to Upload Page", icon="📄")
else:
    st.subheader("Processed Documents")
    summary_df = _summary_table(results)
    st.dataframe(summary_df, use_container_width=True)

    all_flags = _collect_all_flags(results)
    excel_bytes = export_to_excel(results, all_flags)
    csv_text = export_to_csv(results)

    col_excel, col_csv = st.columns(2)
    with col_excel:
        st.download_button(
            label="Download Excel (.xlsx)",
            data=excel_bytes,
            file_name="policylens_results.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
    with col_csv:
        st.download_button(
            label="Download CSV (.csv)",
            data=csv_text,
            file_name="policylens_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
