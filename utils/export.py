"""Export helpers for PolicyLens outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd


def _to_title_case(value: str) -> str:
    """Convert snake_case field names into title case labels.

    Args:
        value: Raw field/key name.

    Returns:
        Human-friendly title-cased label.
    """
    return value.replace("_", " ").title()


def _flatten_result_row(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested result dict into a single export row.

    Args:
        result: Processed result record.

    Returns:
        Flat dictionary suitable for tabular export.
    """
    fields: dict[str, Any] = result.get("fields", {})
    row: dict[str, Any] = {
        "filename": result.get("filename"),
        "doc_type": result.get("doc_type"),
        "page_count": result.get("page_count"),
    }
    for key, value in fields.items():
        if isinstance(value, list):
            row[key] = "; ".join(str(item) for item in value)
        else:
            row[key] = value
    return row


def export_to_excel(results: list[dict[str, Any]], flags: list[dict[str, Any]]) -> BytesIO:
    """Export extracted data and risk flags to a multi-sheet Excel file.

    Args:
        results: List of processed result records.
        flags: Flat list of risk flag records.

    Returns:
        BytesIO buffer positioned at start with the generated XLSX content.
    """
    flattened_rows: list[dict[str, Any]] = [_flatten_result_row(result) for result in results]
    extracted_df = pd.DataFrame(flattened_rows)
    risk_flags_df = pd.DataFrame(flags)

    if not extracted_df.empty:
        extracted_df.columns = [_to_title_case(column) for column in extracted_df.columns]
        extracted_df = extracted_df.where(pd.notna(extracted_df), None)
    if not risk_flags_df.empty:
        risk_flags_df.columns = [_to_title_case(column) for column in risk_flags_df.columns]

    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    if not risk_flags_df.empty and "Severity" in risk_flags_df.columns:
        high_count = int((risk_flags_df["Severity"] == "High").sum())
        medium_count = int((risk_flags_df["Severity"] == "Medium").sum())
        low_count = int((risk_flags_df["Severity"] == "Low").sum())

    summary_df = pd.DataFrame(
        [
            {"Metric": "Total Documents Processed", "Value": len(results)},
            {"Metric": "High Flags", "Value": high_count},
            {"Metric": "Medium Flags", "Value": medium_count},
            {"Metric": "Low Flags", "Value": low_count},
            {"Metric": "Export Timestamp", "Value": datetime.now(timezone.utc).isoformat()},
            {"Metric": "App Version", "Value": "PolicyLens v1.0"},
        ]
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        extracted_df.to_excel(writer, index=False, sheet_name="Extracted Data")
        risk_flags_df.to_excel(writer, index=False, sheet_name="Risk Flags")
        summary_df.to_excel(writer, index=False, sheet_name="Summary")

    output.seek(0)
    return output


def export_to_csv(results: list[dict[str, Any]]) -> str:
    """Export extracted results as flat CSV content.

    Args:
        results: List of processed result records.

    Returns:
        CSV string containing flattened extracted data.
    """
    flattened_rows: list[dict[str, Any]] = [_flatten_result_row(result) for result in results]
    dataframe = pd.DataFrame(flattened_rows)
    if not dataframe.empty:
        dataframe.columns = [_to_title_case(column) for column in dataframe.columns]
    return dataframe.to_csv(index=False)
