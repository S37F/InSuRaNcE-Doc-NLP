"""Rule-based insurance document type classifier."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from config.settings import DOC_TYPE_KEYWORDS
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config.settings import DOC_TYPE_KEYWORDS

logger = logging.getLogger(__name__)


def classify_document(full_text: str) -> str:
    """Classify a document into a supported insurance document type.

    Args:
        full_text: Full extracted text content from the document.

    Returns:
        One of: "policy", "certificate", "endorsement", "claim", or "unknown".
        Returns "unknown" when no configured keywords are matched.
    """
    normalized_text: str = full_text.lower()
    scores: dict[str, int] = {}

    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        hit_count: int = sum(1 for keyword in keywords if keyword.lower() in normalized_text)
        scores[doc_type] = hit_count

    best_doc_type: str = max(scores, key=scores.get) if scores else "unknown"
    best_score: int = scores.get(best_doc_type, 0)

    if best_score <= 0:
        logger.info("Document classification result: unknown (no keyword matches).")
        return "unknown"

    logger.info(
        "Document classified as '%s' with keyword score %d.",
        best_doc_type,
        best_score,
    )
    return best_doc_type


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sample_text: str = (
        "This is to certify that the certificate holder is ACME Corp under "
        "Policy Number POL-123456 as listed on the ACORD form."
    )
    print({"doc_type": classify_document(sample_text)})
