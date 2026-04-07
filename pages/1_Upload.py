"""Upload interface for single and batch document processing."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from core.doc_classifier import classify_document
from core.llm_extractor import extract_entities_llm
from core.nlp_pipeline import extract_entities_spacy
from core.pdf_extractor import extract_pdf
from core.risk_engine import compute_risk_flags

logger = logging.getLogger(__name__)
MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024
SESSION_DEFAULTS: dict[str, Any] = {
    "uploaded_docs": [],
    "extracted_results": [],
    "active_doc_index": 0,
    "chat_history": {},
    "processing_status": {},
}


def _ensure_session_state() -> None:
    """Ensure all required shared session keys exist.

    This page-level guard prevents key errors when the page is loaded
    directly before `app.py` has initialised session defaults.
    """
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            if isinstance(value, dict):
                st.session_state[key] = dict(value)
            elif isinstance(value, list):
                st.session_state[key] = list(value)
            else:
                st.session_state[key] = value


def _validate_upload(uploaded_file: Any) -> tuple[bool, str]:
    """Validate upload constraints before processing.

    Args:
        uploaded_file: Streamlit uploaded file object.

    Returns:
        Tuple of `(is_valid, message)`.
    """
    filename: str = getattr(uploaded_file, "name", "uploaded.pdf")
    lower_name = filename.lower()
    if not lower_name.endswith(".pdf"):
        return False, f"Skipped {filename}: only .pdf files are supported."

    file_size = int(getattr(uploaded_file, "size", 0))
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"Skipped {filename}: file exceeds 20MB limit."
    return True, ""


def _process_uploaded_file(uploaded_file: Any) -> dict[str, Any]:
    """Run end-to-end extraction pipeline for one uploaded file.

    Args:
        uploaded_file: Streamlit uploaded file object.

    Returns:
        Processed result record containing doc info, fields, and flags.
    """
    extraction = extract_pdf(uploaded_file)
    full_text: str = str(extraction.get("full_text", ""))
    doc_type: str = classify_document(full_text)
    spacy_fields = extract_entities_spacy(full_text, doc_type)
    merged_fields = extract_entities_llm(full_text, doc_type, spacy_fields)
    flags = compute_risk_flags(merged_fields, doc_type, str(extraction.get("filename", "unknown.pdf")))
    return {
        "filename": str(extraction.get("filename", "unknown.pdf")),
        "doc_type": doc_type,
        "page_count": int(extraction.get("page_count", 0)),
        "full_text": full_text,
        "pages": extraction.get("pages", []),
        "fields": merged_fields,
        "flags": flags,
    }


def _store_result(result: dict[str, Any]) -> None:
    """Save processed output into session state structures.

    Args:
        result: Fully processed document result.
    """
    filename: str = result["filename"]
    st.session_state["uploaded_docs"].append(
        {
            "filename": filename,
            "raw_text": result["full_text"],
            "pages": result["pages"],
        }
    )
    st.session_state["extracted_results"].append(
        {
            "filename": filename,
            "doc_type": result["doc_type"],
            "page_count": result["page_count"],
            "fields": result["fields"],
            "flags": result["flags"],
        }
    )
    st.session_state["processing_status"][filename] = "done"


def _single_upload_tab() -> None:
    """Render and handle single-document upload workflow."""
    st.subheader("Single Document")
    uploaded_file = st.file_uploader("Upload one PDF document", type=["pdf"], key="single_upload")
    if uploaded_file is None:
        return
    is_valid, message = _validate_upload(uploaded_file)
    if not is_valid:
        st.warning(message)
        return

    progress = st.progress(0, text="Preparing extraction pipeline...")
    try:
        progress.progress(20, text="Extracting PDF text...")
        result = _process_uploaded_file(uploaded_file)
        if not str(result.get("full_text", "")).strip():
            st.warning("Could not extract text from this file.")
            st.session_state["processing_status"][getattr(uploaded_file, "name", "uploaded.pdf")] = "error"
            return
        progress.progress(100, text="Completed.")
        _store_result(result)
        st.success(
            f"Processed {result['filename']} successfully. "
            f"Detected type: {result['doc_type']}."
        )
        if st.button("View Results →", type="primary"):
            st.switch_page("pages/2_Results.py")
    except Exception as exc:
        filename: str = getattr(uploaded_file, "name", "uploaded.pdf")
        logger.error("Single upload processing failed for '%s': %s", filename, exc)
        st.session_state["processing_status"][filename] = "error"
        with st.expander(f"⚠️ Processing Error — {filename}", expanded=True):
            st.error(f"Error type: {type(exc).__name__}")
            st.error(f"Error message: {exc}")
            st.info("Please check the file is a valid, text-based PDF.")


def _batch_upload_tab() -> None:
    """Render and handle batch document upload workflow."""
    st.subheader("Batch Upload")
    uploaded_files = st.file_uploader(
        "Upload multiple PDF documents",
        type=["pdf"],
        accept_multiple_files=True,
        key="batch_upload",
    )
    if not uploaded_files:
        return

    for file_obj in uploaded_files:
        filename: str = getattr(file_obj, "name", "uploaded.pdf")
        if filename not in st.session_state["processing_status"]:
            st.session_state["processing_status"][filename] = "pending"

    st.write("### File Queue")
    for file_obj in uploaded_files:
        filename = getattr(file_obj, "name", "uploaded.pdf")
        status = st.session_state["processing_status"].get(filename, "pending")
        icon = {"pending": "⏳", "done": "✅", "error": "❌"}.get(status, "⏳")
        st.write(f"{icon} {filename} — {status}")

    if not st.button("Process All", type="primary"):
        return

    success_count = 0
    failure_count = 0
    progress = st.progress(0, text="Starting batch processing...")

    with st.status("Processing documents...", expanded=True) as status:
        total_files: int = len(uploaded_files)
        for index, file_obj in enumerate(uploaded_files, start=1):
            filename: str = getattr(file_obj, "name", f"document_{index}.pdf")
            is_valid, message = _validate_upload(file_obj)
            if not is_valid:
                st.session_state["processing_status"][filename] = "error"
                failure_count += 1
                st.warning(message)
                percent = int((index / total_files) * 100)
                progress.progress(percent, text=f"Processed {index}/{total_files} files")
                continue
            try:
                st.session_state["processing_status"][filename] = "pending"
                status.write(f"Processing {filename}...")
                result = _process_uploaded_file(file_obj)
                if not str(result.get("full_text", "")).strip():
                    st.session_state["processing_status"][filename] = "error"
                    failure_count += 1
                    st.warning(f"Could not extract text from {filename}.")
                    continue
                _store_result(result)
                success_count += 1
                status.write(f"Completed {filename}.")
            except Exception as exc:
                logger.error("Batch processing failed for '%s': %s", filename, exc)
                st.session_state["processing_status"][filename] = "error"
                failure_count += 1
                with st.expander(f"⚠️ Processing Error — {filename}", expanded=False):
                    st.error(f"Error type: {type(exc).__name__}")
                    st.error(f"Error message: {exc}")
                    st.info("Please check the file is a valid, text-based PDF.")
            finally:
                percent = int((index / total_files) * 100)
                progress.progress(percent, text=f"Processed {index}/{total_files} files")
        status.update(label="Batch processing complete.", state="complete", expanded=False)

    st.success(f"Batch complete: {success_count} succeeded, {failure_count} failed.")


st.title("📄 Upload Documents")
_ensure_session_state()
tab_single, tab_batch = st.tabs(["Single Document", "Batch Upload"])
with tab_single:
    _single_upload_tab()
with tab_batch:
    _batch_upload_tab()
