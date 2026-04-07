"""PDF extraction utilities for insurance documents."""

from __future__ import annotations

import io
import logging
from typing import BinaryIO

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError

logger = logging.getLogger(__name__)


def extract_pdf(file_obj: BinaryIO) -> dict[str, object]:
    """Extract raw text content from a PDF file object.

    Args:
        file_obj: File-like binary object containing PDF bytes. The object is
            expected to support `read()` and optionally expose a `name` attribute.

    Returns:
        A dictionary with keys:
            - full_text: All page texts joined by newline.
            - pages: Per-page extracted text as a list.
            - page_count: Number of pages in the PDF.
            - filename: Source filename from `file_obj.name` when available.

    Raises:
        ValueError: If no extractable text is found in the PDF.
        PDFSyntaxError: If the PDF is malformed.
        Exception: For any other unexpected extraction failure.
    """
    filename: str = getattr(file_obj, "name", "uploaded.pdf")
    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        raw_bytes: bytes = file_obj.read()
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            pages: list[str] = []
            for page in pdf.pages:
                page_text: str = (page.extract_text() or "").strip()
                pages.append(page_text)

            full_text: str = "\n".join([text for text in pages if text]).strip()
            if not full_text:
                logger.warning("No extractable text found in PDF: %s", filename)
                raise ValueError("No extractable text found in PDF.")

            result: dict[str, object] = {
                "full_text": full_text,
                "pages": pages,
                "page_count": len(pages),
                "filename": filename,
            }
            logger.info(
                "Extracted text from PDF '%s' (%d pages).",
                filename,
                len(pages),
            )
            return result
    except PDFSyntaxError as exc:
        logger.error("PDF syntax error for '%s': %s", filename, exc)
        raise
    except ValueError:
        raise
    except Exception as exc:
        logger.error("Unexpected PDF extraction error for '%s': %s", filename, exc)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sample_pdf = io.BytesIO(b"not a real pdf")
    sample_pdf.name = "sample_invalid.pdf"  # type: ignore[attr-defined]
    try:
        print(extract_pdf(sample_pdf))
    except Exception as exc:
        print(f"Sample run handled extraction error: {exc}")
